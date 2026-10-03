import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'

const metadata = (name: string, description: string) => async () => ({
  name, description, warning: null, allowedStatuses: 'only-running' as const,
  group: 'On-chain Wallet', visibility: 'enabled' as const,
})

async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'wallet-pilot-action', async sub => {
      const response = await sub.exec([
        '/opt/xbt-venv/bin/python', '/usr/local/libexec/wallet_actions.py', rootDir,
      ], { input: JSON.stringify(request) })
      if (response.exitCode !== 0)
        throw new Error('Wallet action refused or interrupted. Check node health and Withdrawal Status. Retain all wallet records; no automatic retry is performed.')
      const result = JSON.parse(String(response.stdout))
      const labels: Record<string, string> = {
        address: 'XBT deposit address', network: 'Network', phase: 'Withdrawal state',
        confirmed_unreserved_sats: 'Confirmed unreserved XBT sats', reserved_outputs: 'Reserved outputs',
        unconfirmed_or_immature_outputs: 'Unconfirmed or immature outputs', destination: 'XBT destination',
        amount_sats: 'Recipient XBT sats', fee_sats: 'Exact transaction fee in XBT sats',
        fee_rate_sat_vbyte: 'Requested fee rate (sat/vbyte)', review_code: 'Review code',
        automatic_retry: 'Automatic retry', inspection_required: 'Local inspection required',
      }
      return {
        version: '1', title: 'XBT On-chain Wallet',
        message: result.phase === 'prepared'
          ? 'No transaction broadcast. Verify the destination, recipient amount and exact fee. To send, enter this review code in Send Prepared Withdrawal. Keep the service running between preparation and send or cancellation.'
          : result.address
            ? 'Use the XBT BLAKE2b chain only. The address prefix is shared with BTC. For this pilot, fund at most 100,000 sats total. The address is reused for this test.'
            : result.phase === 'submitting'
              ? 'Submission outcome is uncertain. Status only checks for confirmation; it never resends. Retain the record and inspect locally.'
              : 'Broadcast means submitted; confirmed means mined. This pilot supports one withdrawal record. Keep private addresses and review codes local.',
        result: { type: 'group', value: Object.entries(result).filter(([k]) => k in labels).map(([k, v]) => ({
          name: labels[k], description: null, type: 'single' as const, value: String(v),
          masked: ['address', 'destination', 'review_code'].includes(k),
          copyable: ['address', 'destination', 'review_code'].includes(k), qr: k === 'address',
        })) },
      }
    })
}

export const depositAddress = sdk.Action.withoutInput('wallet-deposit-address',
  metadata('XBT Deposit Address', 'Get this pilot wallet’s on-chain deposit address. XBT only; maximum pilot balance 100,000 sats.'),
  async ({ effects }) => invoke(effects, { operation: 'address' }))
export const walletFunds = sdk.Action.withoutInput('wallet-funds',
  metadata('Confirmed Wallet Funds', 'Show confirmed unreserved funds and counts of reserved or unconfirmed outputs.'),
  async ({ effects }) => invoke(effects, { operation: 'funds' }))
export const withdrawalStatus = sdk.Action.withoutInput('wallet-withdrawal-status',
  metadata('Withdrawal Status', 'Review the saved withdrawal and check for confirmation. Never prepares or resends a transaction.'),
  async ({ effects }) => invoke(effects, { operation: 'status' }))

const prepareSpec = sdk.InputSpec.of({
  destination: sdk.Value.text({ name: 'XBT return address', description: 'A lowercase bc1q or bc1p address from your XBT wallet. Verify the chain yourself: BTC uses the same prefixes.', required: true, default: null, placeholder: null }),
  feeRate: sdk.Value.number({ name: 'Fee rate', description: 'Explicit fee rate; start with 2 sat/vbyte for the pilot.', required: true, default: 2, min: 2, max: 100, integer: true, units: 'sat/vbyte', placeholder: null }),
  maxFee: sdk.Value.number({ name: 'Maximum total fee', description: 'Preparation must stay within this fee cap. The exact fee is shown before sending.', required: true, default: 2000, min: 1, max: 10000, integer: true, units: 'XBT sats', placeholder: null }),
})
export const prepareWithdrawal = sdk.Action.withInput('wallet-prepare-withdrawal',
  metadata('Prepare Test Withdrawal', 'Reserve all confirmed on-chain funds for return, minus the fee. No broadcast. Requires no channels and at most 100,000 sats total.'),
  prepareSpec, async () => {}, async ({ effects, input }) => invoke(effects, {
    operation: 'prepare', destination: input.destination, fee_rate: input.feeRate, max_fee_sats: input.maxFee,
  }))
const confirmSpec = sdk.InputSpec.of({
  code: sdk.Value.text({ name: 'Review code', description: 'Copy from the prepared withdrawal or Withdrawal Status.', required: true, default: null, placeholder: null }),
  confirmed: sdk.Value.toggle({ name: 'I reviewed the destination, amount and fee', description: 'This applies only to the saved transaction matching the review code.', default: false }),
})
export const sendWithdrawal = sdk.Action.withInput('wallet-send-withdrawal',
  metadata('Send Prepared Withdrawal', 'Sign and broadcast the exact reviewed withdrawal. This spends real XBT.'),
  confirmSpec, async () => {}, async ({ effects, input }) => {
    if (!input.confirmed) throw new Error('Review confirmation required')
    return invoke(effects, { operation: 'send', review_code: input.code })
  })
export const cancelWithdrawal = sdk.Action.withInput('wallet-cancel-withdrawal',
  metadata('Cancel Prepared Withdrawal', 'Discard the prepared transaction and release its inputs. Refuses submitted or uncertain transactions.'),
  confirmSpec, async () => {}, async ({ effects, input }) => {
    if (!input.confirmed) throw new Error('Review confirmation required')
    return invoke(effects, { operation: 'cancel', review_code: input.code })
  })
