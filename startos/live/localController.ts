import { setTimeout as sleep } from 'node:timers/promises'
/** Published local-service contract. Contains only already-approved bounded grants. */
import { randomBytes } from 'node:crypto'
import { access, mkdir, readFile, rename, unlink, writeFile } from 'node:fs/promises'
import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { clnrestPort } from '../utils'
import { clnConfig } from '../fileModels/config'

type Call = (effects: T.Effects, request: Record<string, unknown>) => Promise<any>
const enabledPath = () => sdk.volumes.main.subpath('local-controller-enabled.json')
const publicationPath = () => sdk.volumes.public.subpath('swap-controller.json')
export const localControllerActionId = 'local-swap-controller'
const hex = (v: unknown) => typeof v === 'string' && /^[0-9a-f]{64}$/.test(v)
export async function publication(status: any, profile: string, credential: (id: string) => Promise<any>, now = Date.now()/1000) {
  if (status?.blocked !== false || !Array.isArray(status.reviews)) throw Error('local_setup_unavailable')
  const credentials: Record<string, any> = {}
  for (const kind of ['incoming', 'outgoing']) {
    const matches = status.reviews.filter((r: any) => r.kind === kind && r.phase === 'saved' && r.current === true && r.paused === false && r.expires_at > now)
    if (matches.length > 1) throw Error('local_setup_unavailable')
    if (!matches.length) continue
    const r = matches[0]
    if (!hex(r.confirmation) || r.profile !== profile) throw Error('local_setup_unavailable')
    const c = (await credential(r.confirmation))?.credential
    if (!c || typeof c.rune !== 'string' || !/^[A-Za-z0-9_=-]{32,8192}$/.test(c.rune) || c.grant?.kind !== kind || c.grant?.chain?.profile !== profile || c.grant?.chain?.environment !== 'mainnet') throw Error('local_setup_unavailable')
    credentials[kind] = c
  }
  return { format: 'local-swap-node-v1', profile, hostId: 'clnrest', internalPort: clnrestPort, credentials }
}
export async function clearPublication() {
  await unlink(publicationPath()).catch((e: any) => { if (e.code !== 'ENOENT') throw e })
}
export async function syncLocalController(effects: T.Effects, profile: string, call: Call) {
  try { await access(enabledPath()) } catch { return }
  try {
    // Never reuse a publication after loss of current node/grant evidence.
    const value = await publication(await call(effects, { action: 'status' }), profile,
      id => call(effects, { action: 'credential', grant_id: id, confirmed: true }))
    const raw = JSON.stringify(value)
    if (await readFile(publicationPath(), 'utf8').catch(() => '') === raw) return
    await mkdir(sdk.volumes.public.subpath(''), { recursive: true })
    const tmp = publicationPath()+'.'+randomBytes(8).toString('hex')
    await writeFile(tmp, raw, { mode: 0o600, flag: 'wx' })
    await rename(tmp, publicationPath())
  } catch { await clearPublication() }
}
export function localControllerAction(profile: string, call: Call) {
  return sdk.Action.withInput(localControllerActionId, async () => ({
    name: 'Connect Local Swap Controller', group: 'Swap Coordinator', allowedStatuses: 'only-running' as const,
    visibility: 'enabled' as const, description: 'Automatically share approved bounded grants with Swap Controller on this StartOS server.',
    warning: null,
  }), sdk.InputSpec.of({ enabled: sdk.Value.toggle({ name: 'Allow local controller connection', default: true }) }),
  async () => ({ enabled: await access(enabledPath()).then(() => true, () => false) }),
  async ({ effects, input }) => {
    if (!input.enabled) {
      await unlink(enabledPath()).catch((e: any) => { if (e.code !== 'ENOENT') throw e })
      await clearPublication()
    } else {
      await writeFile(enabledPath(), '{"enabled":true}', { mode: 0o600 })
      const conf = await clnConfig.read().once()
      if (conf?.clnrest !== true) await clnConfig.merge(effects, { clnrest: true })
      await syncLocalController(effects, profile, call)
    }
    return { version: '1' as const, title: 'Local Controller Connection',
      message: input.enabled ? 'Local connection enabled. Enable the Swap Coordinator and confirm incoming and outgoing grants if needed. Approved grants are shared automatically; no URLs, certificates or credentials need copying.'
        : 'Automatic sharing disabled. Existing approved swaps retain their saved recovery credentials. Use Pause Grant to stop new use of a grant.',
      result: { type: 'single' as const, value: input.enabled ? 'Enabled' : 'Disabled', copyable: false, masked: false, qr: false, launchable: false } }
  })
}

export function publicationDaemon(effects: T.Effects, profile: string, call: Call) {
  return {
    subcontainer: null,
    requires: ['lightningd' as const],
    exec: { fn: async (_sub: null, abort: AbortSignal) => {
      while (!abort.aborted) {
        await syncLocalController(effects, profile, call)
        try { await sleep(30000, undefined, { signal: abort }) } catch { break }
      }
      return null
    } },
    ready: { display: null, fn: () => ({ result: 'success' as const, message: 'Local grant publication active.' }) },
  }
}
