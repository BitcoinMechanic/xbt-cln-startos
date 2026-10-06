import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string) => async () => ({
  name, description: 'Dedicated read-only controller access: getinfo and reverse-pilot-info only.',
  warning: null, allowedStatuses: 'only-running' as const,
  group: 'Coordinator Preparation', visibility: 'enabled' as const,
})
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'gate-credential', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/gate_credential.py', rootDir], { input: JSON.stringify(request) })
      const result = JSON.parse(String(response.stdout))
      if (response.exitCode !== 0) throw new Error(result.error + ' Reason: ' + result.reason)
      return { version: '1', title: 'XBT Gate Observation Credential',
        message: 'Use only with a verified HTTPS endpoint. No swap execution authority or new network listener is enabled.',
        result: { type: 'group', value: Object.entries(result).map(([key, value]) => ({
          name: key.replaceAll('_', ' '), description: null, type: 'single' as const,
          value: String(value), masked: key === 'rune', copyable: key === 'rune', qr: false,
        })) },
      }
    })
}
export const gateCredentialStatus = sdk.Action.withInput('gate-credential-status', metadata('XBT Gate Credential Status'),
  sdk.InputSpec.of({}), async () => {}, async ({ effects }) => invoke(effects, { operation: 'status' }))
export const gateCredentialCreate = sdk.Action.withInput('gate-credential-create', metadata('Create or Show XBT Gate Observation Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Create or reveal the read-only credential', description: 'Existing active credential is reused. This grants access to node identity and gate profile and active status.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'create', confirmed: input.confirmed }))
export const gateCredentialRevoke = sdk.Action.withInput('gate-credential-revoke', metadata('Revoke XBT Gate Observation Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Revoke this controller credential', description: 'Disables this rune and its derivatives. Does not revoke unrelated runes.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'revoke', confirmed: input.confirmed }))
