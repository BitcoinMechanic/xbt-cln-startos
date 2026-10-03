import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'

const spec = sdk.InputSpec.of({
  neverFunded: sdk.Value.toggle({
    name: 'This wallet has never received funds or opened channels',
    description: 'Confirm from your own records. An empty restored database alone does not prove this.',
    default: false,
  }),
})

export const finishEmptyRecovery = sdk.Action.withInput(
  'finish-empty-recovery',
  async () => ({
    name: 'Finish Empty-Wallet Recovery',
    description: 'Finish recovery only for a wallet that has NEVER been funded. Stop the service after recovery reaches monitoring.',
    warning: 'Confirm from your own records that this wallet has never been funded. This does not finish funded channel recovery.',
    allowedStatuses: 'only-stopped',
    group: null,
    visibility: 'enabled',
  }),
  spec,
  async () => {},
  async ({ effects, input }) => {
    if (!input.neverFunded) throw new Error('Never-funded confirmation required')
    await sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
      'finish-empty-recovery', async (sub) => {
        const result = await sub.exec([
          '/opt/xbt-venv/bin/python', '/usr/local/libexec/xbt-recovery.py',
          'finish-empty', rootDir, '--confirm-never-funded',
        ])
        if (result.exitCode !== 0)
          throw new Error('Recovery was not finished. It must have a monitoring result from the last ten minutes, no channels and no recorded wallet activity. Retain the wallet and backup.')
      })
    return {
      version: '1',
      title: 'Empty-Wallet Recovery Finished',
      message: 'Start the service to resume normal operation. Wallet data and recovery records were retained.',
      result: null,
    }
  },
)
