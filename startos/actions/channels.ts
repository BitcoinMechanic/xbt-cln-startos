import { T } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { mainMounts, rootDir } from '../utils'

const metadata = (name: string, description: string) => async () => ({
  name, description, warning: null, allowedStatuses: 'only-running' as const,
  group: 'Private Channel Pilot', visibility: 'enabled' as const,
})
const text = (name: string, description: string) => sdk.Value.text({
  name, description, required: true, default: null, placeholder: null,
})
async function invoke(effects: T.Effects, request: object): Promise<T.ActionResult & { version: '1' }> {
  return sdk.SubContainer.withTemp(effects, { imageId: 'lightning' }, mainMounts,
    'channel-pilot-action', async sub => {
      const response = await sub.exec([
        '/opt/xbt-venv/bin/python', '/usr/local/libexec/channel_actions.py', rootDir,
      ], { input: JSON.stringify(request) })
      if (response.exitCode !== 0) {
        let reason = 'Channel action refused or interrupted.'
        try {
          const failure = JSON.parse(String(response.stdout))
          if (typeof failure.error === 'string') reason = failure.error
        } catch {}
        throw new Error(`${reason} Check Channel Status before retrying; retain the saved attempt.`)
      }
      const result = JSON.parse(String(response.stdout))
      const labels: Record<string, string> = {
        next_channel_code: 'Next channel code', phase: 'Saved attempt state', channel_state: 'CLN channel state', channel_sats: 'Channel XBT sats',
        listed_channels: 'Listed channels', peer_connected: 'Peer connected', private: 'Private channel',
        pending_htlcs: 'Pending HTLCs', local_balance_sats: 'Local channel XBT sats',
        funding_pin_saved: 'Funding identity verified and saved', automatic_retry: 'Automatic retry',
        close_review_code: 'Close review code', inspection_required: 'Local inspection required',
        channel_funding_attempted: 'Channel funding attempted',
      }
      return {
        version: '1', title: 'XBT Private Channel Pilot',
        message: result.phase === 'close-confirmed'
          ? 'The cooperative close transaction is confirmed. Check Confirmed Wallet Funds for the returned on-chain balance.'
          : 'CHANNELD_NORMAL means the channel is ready. Funding and close requests are never automatically repeated. Closing uses the exact saved channel; no timeout-triggered force close is requested.',
        result: { type: 'group', value: Object.entries(result).filter(([k]) => k in labels).map(([k, v]) => ({
          name: labels[k], description: null, type: 'single' as const, value: String(v),
          masked: ['close_review_code', 'next_channel_code'].includes(k), copyable: ['close_review_code', 'next_channel_code'].includes(k), qr: false,
        })) },
      }
    })
}
const connectSpec = sdk.InputSpec.of({
  peer: text('XBT peer node ID', 'The full public key from the other XBT node. Keep it separate from host and port.'),
  host: text('Peer host', 'An IP address or DNS hostname reachable from this StartOS box. Tor is not configured by this package yet.'),
  port: sdk.Value.number({ name: 'Peer port', description: 'Use the peer’s advertised Lightning TCP port.', required: true, default: 9735, min: 1, max: 65535, integer: true, placeholder: null }),
})
export const connectPeer = sdk.Action.withInput('channel-connect-peer',
  metadata('Connect XBT Peer', 'Connect to a selected XBT node. Does not fund a channel.'),
  connectSpec, async () => {}, async ({ effects, input }) => invoke(effects, { operation: 'connect', ...input }))
export const channelStatus = sdk.Action.withoutInput('channel-status',
  metadata('Channel Status', 'Reconcile the saved pilot funding or close attempt and show channel readiness. No funding or close RPC is sent.'),
  async ({ effects }) => invoke(effects, { operation: 'status' }))
const openSpec = sdk.InputSpec.of({
  previous: sdk.Value.text({ name: 'Previous close code', description: 'Leave blank for the first channel. Otherwise archive the confirmed close and copy Next channel code from Channel Status.', required: false, default: null, placeholder: null }),
  peer: text('Connected XBT peer node ID', 'Verify this public key belongs to your intended peer.'),
  amount: sdk.Value.number({ name: 'Channel amount', description: 'A private channel; no funds are gifted to the peer. Pilot range 20,000–80,000 sats.', required: true, default: 50000, min: 20000, max: 80000, integer: true, units: 'XBT sats', placeholder: null }),
  feeRate: sdk.Value.number({ name: 'Funding fee rate', description: 'Funding fees are additional to the channel amount. Keep at least 10,000 sats extra in the wallet. Larger wallet balances are accepted; excess funds return as change. Fee rate is limited to 2–10 sat/vbyte.', required: true, default: 2, min: 2, max: 10, integer: true, units: 'sat/vbyte', placeholder: null }),
  confirmed: sdk.Value.toggle({ name: 'I authorize this private channel and its funding fee', description: 'Opening spends on-chain funds and locks the channel amount in a Lightning channel.', default: false }),
})
export const openChannel = sdk.Action.withInput('channel-open-private',
  metadata('Open Private Test Channel', 'Fund one private channel with the connected peer. This submits a real on-chain transaction.'),
  openSpec, async () => {}, async ({ effects, input }) => invoke(effects, {
    operation: 'open', peer: input.peer, amount_sats: input.amount, fee_rate: input.feeRate, confirmed: input.confirmed, previous_close_code: input.previous || '',
  }))
const closeSpec = sdk.InputSpec.of({
  code: text('Close review code', 'Copy from Channel Status for this saved channel.'),
  confirmed: sdk.Value.toggle({ name: 'I authorize cooperative closure of this channel', description: 'Requires a connected normal channel with no pending HTLCs. Closing incurs an on-chain fee.', default: false }),
})
export const closeChannel = sdk.Action.withInput('channel-close-private',
  metadata('Cooperatively Close Test Channel', 'Close the exact saved channel. No automatic force-close timeout; peer cooperation is required.'),
  closeSpec, async () => {}, async ({ effects, input }) => invoke(effects, {
    operation: 'close', review_code: input.code, confirmed: input.confirmed,
  }))

export const archiveChannel = sdk.Action.withInput('channel-archive-closed',
  metadata('Archive Confirmed Channel Close', 'Preserve the completed attempt and enable review of another channel. Does not fund or close anything.'),
  sdk.InputSpec.of({ code: text('Close review code', 'Copy from Channel Status for the confirmed close.'), confirmed: sdk.Value.toggle({ name: 'Archive this completed channel attempt', description: 'Preserves its funding and close record; a new channel requires separate authorization.', default: false }) }), async () => {}, async ({ effects, input }) => invoke(effects, {
    operation: 'archive', review_code: input.code, confirmed: input.confirmed,
  }))
