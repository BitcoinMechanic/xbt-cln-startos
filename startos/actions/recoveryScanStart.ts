import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'

const spec = sdk.InputSpec.of({
  height: sdk.Value.number({
    name: 'Scan starting block height',
    description: 'A positive height safely BEFORE this wallet was created. Do not enter the current tip.',
    default: null,
    integer: true,
    required: true,
    placeholder: '974000',
  }),
  neverFunded: sdk.Value.toggle({
    name: 'This wallet has never received funds or opened channels',
    description: 'Confirm from your own records. An empty restored database alone does not prove this.',
    default: false,
  }),
})

export const recoveryScanStart = sdk.Action.withInput(
  'recovery-scan-start',
  async () => ({
    name: 'Set Empty-Wallet Recovery Scan Start',
    description: 'Shorten a pending restore scan for a wallet you know has NEVER been funded. Stop the service first.',
    warning: 'A height after wallet creation can skip deposits. This action is only for a never-funded wallet, not general channel recovery.',
    allowedStatuses: 'only-stopped',
    group: null,
    visibility: 'enabled',
  }),
  spec,
  async () => {},
  async ({ effects, input }) => {
    if (!input.neverFunded || !Number.isSafeInteger(input.height) || input.height < 1 || input.height > 2147483647)
      throw new Error('Enter a positive starting height and confirm this wallet has never been funded')
    await sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
      'set-recovery-scan-start', async (sub) => {
        const result = await sub.exec([
          '/opt/xbt-venv/bin/python', '/usr/local/libexec/xbt-recovery.py',
          'set-empty-scan-start', rootDir, String(input.height), '--confirm-never-funded',
        ])
        if (result.exitCode !== 0)
          throw new Error('Scan start was not changed: recovery must be unimported, channel-free and have no recorded activity. Keep the wallet and backup.')
      })
    return {
      version: '1',
      title: 'Recovery Scan Start Saved',
      message: `Start the service to scan from block ${input.height}. No database or backup was deleted.`,
      result: null,
    }
  },
)
