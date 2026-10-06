import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string) => async () => ({
  name, description: 'Dedicated read-only controller access: getinfo, listfunds, listpeerchannels, decode and listsendpays only.',
  warning: null, allowedStatuses: 'only-running' as const,
  group: 'Coordinator Preparation', visibility: 'enabled' as const,
})
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'inspection-credential', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/inspection_credential.py', rootDir], { input: JSON.stringify(request) })
      let result: any
      try { result = JSON.parse(String(response.stdout)) }
      catch { throw new Error('Inspection credential unavailable; private details withheld.') }
      if (response.exitCode !== 0) throw new Error('Inspection credential unavailable; private details withheld.')
      return { version: '1', title: 'XBT Inspection Credential',
        message: 'Use only with a verified HTTPS endpoint. No swap execution authority or new network listener is enabled.',
        result: { type: 'group', value: Object.entries(result).filter(([key]) => ['phase', 'rune', 'read_only', 'payment_started'].includes(key)).map(([key, value]) => ({
          name: key.replaceAll('_', ' '), description: null, type: 'single' as const,
          value: String(value), masked: key === 'rune', copyable: key === 'rune', qr: false,
        })) },
      }
    })
}
export const inspectionCredentialStatus = sdk.Action.withInput('inspection-credential-status', metadata('XBT Inspection Credential Status'),
  sdk.InputSpec.of({}), async () => {}, async ({ effects }) => invoke(effects, { operation: 'status' }))
export const inspectionCredentialCreate = sdk.Action.withInput('inspection-credential-create', metadata('Create or Show XBT Inspection Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Create or reveal the read-only credential', description: 'Existing active credential is reused. This grants access to node identity, wallet reserves, channels, decoded invoices and payment attempts.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'create', confirmed: input.confirmed }))
export const inspectionCredentialRevoke = sdk.Action.withInput('inspection-credential-revoke', metadata('Revoke XBT Inspection Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Revoke this controller credential', description: 'Disables this rune and its derivatives. Does not revoke unrelated runes.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'revoke', confirmed: input.confirmed }))
