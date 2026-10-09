import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string) => async () => ({
  name, description: 'Preparation only. Does not activate swap gates or spend funds.',
  warning: null, allowedStatuses: 'only-running' as const,
  group: 'Swap Setup', visibility: 'enabled' as const,
})
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'coordinator-preparation', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/coordinator.py', rootDir], { input: JSON.stringify(request) })
      const result = JSON.parse(String(response.stdout))
      if (response.exitCode !== 0) throw new Error(result.error)
      return { version: '1', title: 'Coordinator Preparation',
        message: 'Controller pairing is still required. This action does not enable live swaps.',
        result: { type: 'group', value: Object.entries(result).map(([key, value]) => ({
          name: key.replaceAll('_', ' '), description: null, type: 'single' as const,
          value: String(value), masked: false, copyable: false, qr: false,
        })) },
      }
    })
}
export const coordinatorStatus = sdk.Action.withInput('coordinator-status', metadata('Coordinator Readiness'),
  sdk.InputSpec.of({}), async () => {}, async ({ effects }) => invoke(effects, { operation: 'status' }))
export const prepareCoordinator = sdk.Action.withInput('coordinator-prepare', metadata('Prepare Coordinator'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Prepare this node for later controller pairing', description: 'Saves an identity-bound receipt. No swap gate is activated.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'prepare', confirmed: input.confirmed }))
