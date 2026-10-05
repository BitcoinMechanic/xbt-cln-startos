import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string) => async () => ({
  name, description: 'Dedicated read-only controller access: getinfo and listpeerchannels only.',
  warning: null, allowedStatuses: 'only-running' as const,
  group: 'Coordinator Preparation', visibility: 'enabled' as const,
})
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'controller-credential', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/controller_credential.py', rootDir], { input: JSON.stringify(request) })
      const result = JSON.parse(String(response.stdout))
      if (response.exitCode !== 0) throw new Error(result.error + ' Reason: ' + result.reason)
      return { version: '1', title: 'Read-only Controller Credential',
        message: 'Use only with a verified HTTPS endpoint. No swap execution authority or new network listener is enabled.',
        result: { type: 'group', value: Object.entries(result).map(([key, value]) => ({
          name: key.replaceAll('_', ' '), description: null, type: 'single' as const,
          value: String(value), masked: key === 'rune', copyable: key === 'rune', qr: false,
        })) },
      }
    })
}
export const controllerCredentialStatus = sdk.Action.withInput('controller-credential-status', metadata('Controller Credential Status'),
  sdk.InputSpec.of({}), async () => {}, async ({ effects }) => invoke(effects, { operation: 'status' }))
export const controllerCredentialCreate = sdk.Action.withInput('controller-credential-create', metadata('Create or Show Read-only Controller Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Create or reveal the read-only credential', description: 'Existing active credential is reused. This grants access to node and channel information.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'create', confirmed: input.confirmed }))
export const controllerCredentialRevoke = sdk.Action.withInput('controller-credential-revoke', metadata('Revoke Read-only Controller Credential'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Revoke this controller credential', description: 'Disables this rune and its derivatives. Does not revoke unrelated runes.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'revoke', confirmed: input.confirmed }))
