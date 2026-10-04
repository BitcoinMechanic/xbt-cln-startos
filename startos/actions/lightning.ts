import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'
const metadata = (name: string, description: string) => async () => ({
  name, description, warning: null, allowedStatuses: 'only-running' as const,
  group: 'Lightning Payments', visibility: 'enabled' as const,
})
const text = (name: string, description: string) => sdk.Value.text({ name, description, required: true, default: null, placeholder: null })
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'lightning-wallet-action', async sub => {
      const response = await sub.exec(['/opt/xbt-venv/bin/python', '/usr/local/libexec/lightning_actions.py', rootDir], { input: JSON.stringify(request) })
      const r = JSON.parse(String(response.stdout))
      if (response.exitCode !== 0) throw new Error(r.error || 'Check payment status before retrying.')
      return { version: '1', title: 'XBT Lightning',
        message: 'Amounts ending in msat are millisatoshis (1,000 msat = 1 XBT sat). Review the destination, amount and maximum fee before authorizing. Save the payment reference and review code. Submitted attempts are only inspected when repeated; failed or unknown attempts are not resubmitted.',
        result: { type: 'group', value: Object.entries(r).map(([k, v]) => ({
          name: k.replaceAll('_', ' '), description: null, type: 'single' as const, value: String(v),
          masked: ['invoice', 'payee', 'reference', 'review_code'].includes(k),
          copyable: ['invoice', 'payee', 'reference', 'review_code', 'label'].includes(k), qr: k === 'invoice',
        })) },
      }
    })
}
const label = text('Invoice label', 'A unique name (letters, numbers, hyphens, underscores). Reusing a label returns its original invoice.')
const reference = text('Payment reference', 'Copy the full reference from Review Lightning Payment. Retain it even if submission is interrupted.')
export const createInvoice = sdk.Action.withInput('lightning-create-invoice', metadata('Create XBT Invoice', 'Create or retrieve a one-hour invoice for 1–10,000 XBT sats.'),
  sdk.InputSpec.of({ label, amount: sdk.Value.number({ name: 'Amount', description: 'XBT sats to receive.', required: true, default: 1000, min: 1, max: 10000, integer: true, placeholder: null }) }), async () => {},
  async ({ effects, input }) => invoke(effects, { operation: 'invoice', label: input.label, amount_sats: input.amount }))
export const invoiceStatus = sdk.Action.withInput('lightning-invoice-status', metadata('XBT Invoice Status', 'Check a previously created invoice by label. No new invoice or payment.'), sdk.InputSpec.of({ label }), async () => {},
  async ({ effects, input }) => invoke(effects, { operation: 'invoice_status', ...input }))
export const reviewPayment = sdk.Action.withInput('lightning-review-payment', metadata('Review Lightning Payment', 'Decode and save an XBT BOLT11 invoice, up to 10,000 sats. Does not pay.'),
  sdk.InputSpec.of({ invoice: text('XBT invoice', 'Paste the complete invoice. Amountless, BTC and description-hash invoices are refused.'),
    fee: sdk.Value.number({ name: 'Maximum routing fee', description: 'Absolute additional fee in XBT sats. Maximum route delay is 144 blocks.', required: true, default: 1, min: 0, max: 100, integer: true, placeholder: null }) }), async () => {},
  async ({ effects, input }) => invoke(effects, { operation: 'review', invoice: input.invoice.trim(), max_fee_sats: input.fee }))
export const payInvoice = sdk.Action.withInput('lightning-pay-invoice', metadata('Pay Reviewed Lightning Invoice', 'Authorize the saved amount and fee. Repeated submissions only check status.'),
  sdk.InputSpec.of({ reference, code: text('Review code', 'Copy from the saved review.'), confirmed: sdk.Value.toggle({ name: 'I authorize the reviewed payment and fee cap', description: 'This spends XBT from your Lightning wallet.', default: false }) }), async () => {},
  async ({ effects, input }) => invoke(effects, { operation: 'pay', reference: input.reference, review_code: input.code, confirmed: input.confirmed }))
export const paymentStatus = sdk.Action.withInput('lightning-payment-status', metadata('Lightning Payment Status', 'Inspect a saved payment. Never submits or retries a payment.'), sdk.InputSpec.of({ reference }), async () => {},
  async ({ effects, input }) => invoke(effects, { operation: 'status', ...input }))
