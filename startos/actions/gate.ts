import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string) => async () => ({
  name, description: 'XBT incoming swap gate. Grants and per-swap confirmation authorize execution separately.',
  warning: null, allowedStatuses: 'only-running' as const,
  group: 'Swap Setup', visibility: 'enabled' as const,
})
async function invoke(effects: T.Effects, operation: string, confirmed = false): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'xbt-gate-action', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/gate.py', operation, rootDir], { input: JSON.stringify({ confirmed }) })
      const result = JSON.parse(String(response.stdout))
      if (response.exitCode !== 0) throw new Error(result.error + ' Reason: ' + result.reason)
      return { version: '1', title: 'XBT Swap Gate',
        message: 'If restart required is true, restart XBT Core Lightning and run XBT Swap Gate Status. Gate activation does not grant payment authority or publish an invoice.',
        result: { type: 'group', value: Object.entries(result).map(([key, value]) => ({
          name: key.replaceAll('_', ' '), description: null, type: 'single' as const,
          value: String(value), masked: false, copyable: false, qr: false,
        })) },
      }
    })
}
export const xbtGateStatus = sdk.Action.withInput('xbt-gate-status', metadata('XBT Swap Gate Status'),
  sdk.InputSpec.of({}), async () => {}, async ({ effects }) => invoke(effects, 'status'))
export const activateXbtGate = sdk.Action.withInput('xbt-gate-activate', metadata('Enable Bounded XBT Swap Gate'),
  sdk.InputSpec.of({ confirmed: sdk.Value.toggle({ name: 'Enable the XBT gate (one active quote) on the next service restart', description: 'Underlying gate ceiling: 1,500 BTC sats payout; incoming XBT limited to 500,000 sats; routing fee bound 30 BTC sats. The current reverse swap grant applies its stricter 3,000 XBT sat input and 10 BTC sat routing fee bounds. Each swap still requires separate approval. Does not publish an invoice, create credentials or start a payment. Requires Prepare Coordinator; restored gates stay blocked.', default: false }) }),
  async () => {}, async ({ effects, input }) => invoke(effects, 'activate', input.confirmed))
