import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../volume'

export const profile = 'xbt-privkeyio-v1'
export const directory = rootDir + '/regtest'
export const adminCommand = ['/usr/local/libexec/swap-node/package_admin.py', '--disposable-regtest', '--network-directory', directory, '--profile', profile]
export type Call = (effects: T.Effects, request: Record<string, unknown>) => Promise<any>
const refuse = () => new Error('Coordinator request refused or reply unavailable. Inspect grant status and preserve its records. Private details withheld.')
const hex = (v: unknown): v is string => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v)
export async function executeRequest(request: Record<string, unknown>, exec: (argv: string[], options?: { input: string }) => Promise<any>) {
    const run = async (argv: string[], options?: { input: string }) => {
      try { return await exec(argv, options) } catch { throw refuse() }
    }
    if (request.action === 'credential') {
      if (!hex(request.grant_id) || request.confirmed !== true || Object.keys(request).sort().join() !== 'action,confirmed,grant_id') throw refuse()
      const cli = ['/opt/xbt/bin/lightning-cli', '--lightning-dir=' + rootDir, '--network=regtest', '--json', '--notifications=none', '-k']
      const ask = async (method: string, args: string[]) => {
        const r = await run([...cli, method, ...args])
        if (r.exitCode !== 0) throw refuse()
        try { return JSON.parse(String(r.stdout)) } catch { throw refuse() }
      }
      const credential = await ask('swap-customer-credential', ['grant_id=' + request.grant_id, 'confirmed=true'])
      const info = await ask('swap-customer-call', ['grant_id=' + request.grant_id, 'operation=info', 'body={}'])
      if (typeof credential?.rune !== 'string' || !/^[A-Za-z0-9_=-]{32,8192}$/.test(credential.rune) || info?.regtest_only !== true ||
          info?.grant?.chain?.profile !== profile || info?.grant?.chain?.environment !== 'regtest') throw refuse()
      return { credential: { grant: info.grant, rune: credential.rune } }
    }
    const r = await run(adminCommand, { input: JSON.stringify(request) })
    if (r.exitCode !== 0) throw refuse()
    try { return JSON.parse(String(r.stdout)) } catch { throw refuse() }
}
export const invoke: Call = async (effects, request) => sdk.SubContainer.withTemp(
  effects, { imageId: 'lightning' }, mainMounts, 'migrated-grant-action', sub => executeRequest(request, (argv, options) => sub.exec(argv, options)))
const text = (name: string) => sdk.Value.text({ name, masked: false, required: true, default: null, placeholder: null })
const number = (name: string, value: number, min: number, max: number) => sdk.Value.number({ name, default: value, required: true, integer: true, min, max })
const confirm = () => sdk.Value.toggle({ name: 'Confirm this exact grant and its channel protection authority', default: false })
const meta = (name: string) => async () => ({ name, group: 'Swap Coordinator', allowedStatuses: 'only-running' as const,
  visibility: 'enabled' as const, description: 'Migrated coordinator integration candidate. Disposable regtest only.',
  warning: 'Incoming protection may force-close the actual receiving channel, including other payments, near the agreed deadline.' })
export function display(report: any): T.ActionResult & { version: '1' } {
  if (!report || typeof report !== 'object') throw refuse()
  const rows: any[] = []
  const add = (name: string, value: string, copyable = false, masked = false) => rows.push({ name, value, copyable, masked, type: 'single', description: null, qr: false })
  if (report.credential) {
    const c = report.credential
    if (typeof c.rune !== 'string' || !c.grant || c.grant.chain?.profile !== profile || c.grant.chain?.environment !== 'regtest') throw refuse()
    add('Bounded controller credential', JSON.stringify({ grant: c.grant, rune: c.rune }), true, true)
  }
  const records = Array.isArray(report.reviews) ? report.reviews : [report]
  for (const r of records) {
    if (hex(r?.confirmation)) add('Grant confirmation', r.confirmation, true)
    if (['incoming', 'outgoing'].includes(r?.kind)) add('Role', r.kind)
    if (['review', 'intent', 'saved', 'cancelled'].includes(r?.phase)) add('Phase', r.phase)
    for (const k of ['blocked', 'current', 'paused', 'initialized', 'recovery_preserved']) if (typeof r?.[k] === 'boolean') add(k, String(r[k]))
    if (Number.isSafeInteger(r?.channel_count) && r.channel_count >= 0 && r.channel_count <= 8) add('Automatically selected channels', String(r.channel_count))
    for (const k of ['max_swaps', 'max_amount_msat', 'total_amount_msat', 'max_fee_msat', 'max_delay_blocks', 'max_hops', 'min_cltv_delta', 'max_cltv_delta', 'close_before_blocks']) {
      if (Number.isSafeInteger(r?.limits?.[k]) && r.limits[k] >= 0) add(k, String(r.limits[k]))
    }
    for (const k of ['expires_at', 'confirm_before']) if (Number.isSafeInteger(r?.[k]) && r[k] >= 0 && r[k] <= 2 ** 35) add(k + ' (UTC)', new Date(r[k] * 1000).toISOString())
  }
  return { version: '1', title: 'Coordinator Grant', message: 'Review the automatically selected channels and bounded amounts, then confirm the exact grant. Existing swap records remain recoverable.', result: { type: 'group', value: rows } }
}
export function createActions(call: Call = invoke) {
  let actions = sdk.Actions.of()
  const add = (a: any) => { actions = actions.addAction(a) }
  add(sdk.Action.withInput('migrated-admin-init', meta('Initialize Grant Administration'), sdk.InputSpec.of({ confirmed: confirm() }), async () => ({ confirmed: false }),
    async ({ effects, input }) => {
      if (input.confirmed !== true) throw refuse()
      return display(await call(effects, { action: 'initialize', confirmed: true }))
    }))
  for (const kind of ['incoming', 'outgoing'] as const) {
    const bounds = { maxSwaps: number('Maximum swaps', 4, 1, 10), maxAmount: number('Maximum amount per swap (millisats)', 10000000, 1, 1000010000),
      totalAmount: number('Total grant budget (millisats)', 30000000, 1, 10000100000), lifetime: number('Grant lifetime (seconds)', 86400, 300, 86400) }
    const timing: Record<string, ReturnType<typeof number>> = kind === 'incoming' ? { minDelay: number('Minimum incoming delay (blocks)', 350, 216, 2016), maxDelay: number('Maximum incoming delay (blocks)', 2016, 216, 2016) }
      : { maxFee: number('Maximum routing fee (millisats)', 10000, 0, 10000), maxDelay: number('Maximum outgoing delay (blocks)', 288, 1, 288), maxHops: number('Maximum hops', 4, 1, 4) }
    add(sdk.Action.withInput('migrated-review-' + kind, meta('Review ' + kind + ' Grant'), sdk.InputSpec.of({ ...bounds, ...timing }), async () => {},
      async ({ effects, input }: any) => {
        if (input.totalAmount < input.maxAmount) throw new Error('The total budget must cover at least one swap at the per-swap maximum.')
        if (kind === 'incoming' && input.maxDelay < input.minDelay) throw new Error('The maximum incoming delay must be at least the minimum.')
        const limits = { max_swaps: input.maxSwaps, max_amount_msat: input.maxAmount, total_amount_msat: input.totalAmount,
          ...(kind === 'incoming' ? { min_cltv_delta: input.minDelay, max_cltv_delta: input.maxDelay, close_before_blocks: 72 }
            : { max_fee_msat: input.maxFee, max_delay_blocks: input.maxDelay, max_hops: input.maxHops }) }
        return display(await call(effects, { action: 'review', kind, limits, lifetime_seconds: input.lifetime }))
      }))
  }
  for (const action of ['confirm', 'cancel', 'pause', 'credential'] as const) add(sdk.Action.withInput('migrated-grant-' + action,
    meta({ confirm: 'Confirm Reviewed Grant', cancel: 'Cancel Grant Review', pause: 'Pause Grant', credential: 'Show Bounded Controller Credential' }[action]),
    sdk.InputSpec.of({ confirmation: text('Exact grant confirmation'), confirmed: confirm() }), async () => ({ confirmed: false }),
    async ({ effects, input }) => {
      if (!hex(input.confirmation) || input.confirmed !== true) throw refuse()
      const field = action === 'pause' || action === 'credential' ? 'grant_id' : 'confirmation'
      return display(await call(effects, { action, [field]: input.confirmation, ...(action === 'cancel' ? {} : { confirmed: true }) }))
    }))
  add(sdk.Action.withInput('migrated-grant-status', meta('Grant Status'), sdk.InputSpec.of({}), async () => {}, async ({ effects }) => display(await call(effects, { action: 'status' }))))
  return actions
}
export const actions = createActions()
