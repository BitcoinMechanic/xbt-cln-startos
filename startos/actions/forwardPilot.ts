import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const meta = async () => ({
  name: 'Authorize XBT Forward Pilot', group: 'Advanced / Legacy',
  description: 'Authorize the exact reviewed 1,000 BTC sat to 2,000 XBT sat pilot contract. This credential has spending or protection authority.',
  warning: 'Only authorize the contract you reviewed in Swap Controller. Existing channels may be force-closed if deadline protection is needed.',
  allowedStatuses: 'only-running' as const, visibility: 'enabled' as const,
})
export const authorizeForwardPilot = sdk.Action.withInput('authorize-forward-pilot', meta, sdk.InputSpec.of({
  contract: sdk.Value.text({ name: 'Reviewed pilot contract JSON', masked: true, required: true, default: null, placeholder: null }),
  confirmed: sdk.Value.toggle({ name: 'Authorize this exact pilot contract', default: false }),
}), async () => {}, async ({ effects, input }) =>
  sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts, 'forward-pilot-authority', async sub => {
    let contract: unknown
    try { contract = JSON.parse(input.contract) } catch { throw new Error('Invalid pilot contract JSON.') }
    const res = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/pilot_node.py', 'xbt', rootDir, 'authorize'], { input: JSON.stringify({ contract, confirmed: input.confirmed }) })
    let report: any
    try { report = JSON.parse(String(res.stdout)) } catch { throw new Error('Pilot authorization unavailable; private details withheld.') }
    if (res.exitCode !== 0) throw new Error('Pilot authorization refused or uncertain. Preserve the current records.')
    return { version: '1' as const, title: 'XBT Forward Pilot Authority',
      message: 'Copy this pilot ID and credential to Swap Controller. No payment has been submitted by this action.',
      result: { type: 'group' as const, value: ['pilot_id','rune','payment_started'].map(key => ({
        name: key, description: null, type: 'single' as const, value: String(report[key]),
        masked: key === 'rune', copyable: key !== 'payment_started', qr: false,
      })) },
    }
  }))
