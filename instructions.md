# XBT Core Lightning

## Market pricing (0064)

After the packaging VM reports READY, finish any active swap and install all
three packages: BTC 26.6.9:9, XBT 0.1.0:27 and Swap Controller 0.1.0:24.
Existing fixed-price grants and historical records retain their original terms.

To use Neoxa pricing for a direction, explicitly create new grants on **both**
coordinators under **Swap Grants**. Enable **Neoxa market-priced swaps**, choose
matching per-swap and total BTC/XBT limits, and enable **New grant** when replacing
an existing grant. Finish all existing swaps first. Leave the channel field empty
for the normal routed flow. Follow any requested coordinator restart, then pair
both credentials for that direction in **Swap Controller → Swap Setup**.
Do not delete old swap records or reuse an old grant as market authority.

In **Swap Setup → Market Pricing**, operator markup defaults to **0%**. The field
uses basis points: 0 = 0%, 100 = 1%, 500 = 5%. Changes affect new quotes only.
The coordinator's selected outgoing routing fee is included before markup and
whole-satoshi rounding. Fees paid by your sending wallet are additional. The
exchange bid/ask spread still applies at 0% markup. No exchange account or
trading credentials are needed; this does not place a trade on Neoxa.

Use a fresh recipient invoice for a whole number of sats, within the saved
grant limits, with at least 33 minutes remaining and final CLTV at most 40.
Include private routing hints where needed. Then:

- **New BTC to XBT Swap** → review → **Confirm BTC to XBT Swap** → pay BTC.
- **New XBT to BTC Swap** → review → **Confirm XBT to BTC Swap** → pay XBT.

Review both amounts, the Neoxa price, markup, route fee and expiry. A quote lasts
**two minutes from the price fetch**, including review and payment. Confirm and
pay before that deadline. An expired unapproved draft can be cancelled and a
new quote requested; it is never silently repriced. No SCID entry is needed in
the controller. One payment part and one outgoing attempt are supported.

BTC → XBT uses available Neoxa asks; XBT → BTC uses bids. Quotes require enough
ordinary order-book depth and fresh, plausible ticker data. Synthetic AMM levels
are excluded. Stale/unavailable data or insufficient depth stops new market
quotes; there is no fallback to the old fixed rate. This price is a reference
for the swap, not an exchange fill guarantee or an automatically hedged trade.

Default market limits are 10,000 BTC sats / 500,000 XBT sats per swap and
50,000 BTC sats / 2,500,000 XBT sats over the grant. Outgoing fees count toward
these limits. Choose smaller limits if appropriate. Approval reserves one slot
and the quoted amounts; failed or expired approved swaps do not replenish them.
Grant enrollment still expires after 24 hours. Pause/expiry blocks new swaps
while preserving the recovery rights of already enrolled swaps.

**Swap Status** is read-only and shows expiry, slots, market limits and remaining
amount budgets. It does not guarantee a route. Route limits remain four hops,
10 sats of the outgoing asset, and 80 blocks forward / 288 blocks for new
reverse grants. Existing direct/fixed grants keep their old caps and fixed
1,000 BTC → 2,000 XBT or 3,000 XBT → 1,500 BTC amounts.

Check the appropriate swap history and recipient receipt after paying. If a
reply is uncertain, preserve the record and let the worker recover the original
attempt; do not repeat the payment. Accepted payments keep their saved amounts,
route and incoming-channel binding across restarts and price-source outages.
On-chain recovery requires separate claim/sweep verification; it is not a
settled result. Historical pilot tools remain hidden unless an older record
requires inspection. **Advanced / Recovery → Worker Status** remains available.


This is an experimental XBT (BLAKE2b) Lightning node, distinct from Bitcoin Core
Lightning. It requires a synced, unpruned BLAKE2b Knots service on the same StartOS
box. A service called `bitcoind` is not sufficient: startup checks its chain.

Use a fresh installation. Do not import an existing node. Use only the bounded
private-channel action below when testing channels.
Version 0.1.0:6 supports a small on-chain deposit/return pilot, limited to
100,000 sats total. Follow the wallet-action procedure below.

The **XBT Node** health check reports readiness. **Node Info** displays the node
ID and available peer addresses. There is no web wallet UI in this release.
The swap controller and coordinator roles are not installed by this package yet.

This release supports a backup/restore test of the empty observation wallet:

1. Install the current version, start it, and privately record its Node Info ID.
2. Use StartOS to back up XBT Core Lightning. StartOS stops and restarts the
   service for the backup; wait until it reports success.
3. Keep that backup intact. Restore testing requires a fresh installation/volume;
   do not restore over an existing wallet database. Do not uninstall the original
   until the successful backup has been confirmed and the restore procedure chosen.
4. After restoration, start the service. Green XBT Node health requires the
   restored ID to match the backup. Confirm the same ID in Node Info as well.

The original 0.1.0:1 profile refuses recorded wallet/channel activity; see the
0.1.0:2 limits below.
Backups made by 0.1.0:0 lack the new receipt and cannot be used for this test.
A missing or changed key/recovery file blocks restoration. Keep both the original
and backup when any check fails; do not delete the restore-blocked marker.

Your tower coordinators and customer VM continue to operate separately.

The development recovery test uses disposable regtest coins inside an isolated
Docker container. It validates recovery helper behavior separately from the StartOS lifecycle. The empty-wallet restore has been verified to
retain the node ID.


Version 0.1.0:2 introduced experimental recovery orchestration. The Docker test
exercises the same backup/restore helpers as the package.

Supported backups are limited to settled normal channels with no pending HTLCs,
no inflight funding or reserved/unconfirmed outputs, and wallet address indices
at most 50. A refused backup must not be treated as successful. Retain the
original wallet and the last successful backup.

Restoring this backup sacrifices the channels: the new instance rescans the
chain and asks surviving peers to force-close. It cannot continue those channels
from an old database. Never run both the original and restored wallet together.
An unavailable peer can delay recovery indefinitely. The XBT Recovery health
check remains pending until funds have been manually verified; it reports
waiting peer closes and on-chain channels without claiming recovery is complete.
Do not clear markers by hand or open new channels on the recovery instance.


### Shortening a never-funded restore scan (0.1.0:3)

If you restored this newly created observation wallet and it is scanning from
block one, stop the service, open **Actions → Set Empty-Wallet Recovery Scan Start**,
and enter a positive block height safely before you first created this wallet.
Confirm that the key has never received funds or opened channels. Start the service
again. No database or backup is deleted. The health check shows the scan height.

Use this action only when you know the wallet was never funded; do not infer that
from an empty restored balance. It refuses recorded activity, expected channels,
or an already imported recovery. A future block height is refused at startup.
New wallets created by 0.1.0:3 automatically record a conservative starting height
for subsequent backups; existing wallets retain their original default.


Version 0.1.0:4 fixes a missing recovery worker in 0.1.0:2–3. Upgrade the existing
installation and start it; keep the saved scan height and restored data. No new
restore or scan-start action is needed. Once XBT Node is ready, a separate
**XBT Recovery** health check should appear. Pending/manual review is expected;
green XBT Node by itself does not mean recovery has run.

## Finish a never-funded wallet restore

Version 0.1.0:5 adds **Finish Empty-Wallet Recovery** under Actions. Use it only
when your own records confirm this wallet has NEVER received funds or opened a
channel. An empty restored database does not establish that fact.

Let the node finish syncing and the recovery check reach monitoring with zero
channels. Stop the service, run the action within ten minutes, confirm the
never-funded statement, then start the service. If monitoring is stale, start
the service to refresh it, then stop and retry.

The action requires the recovery worker to be stopped, verifies the key and
database identity, and refuses recorded channel, HTLC, output, transaction,
payment or invoice activity. It retains the database, key, backup and recovery
records. A durable `finished-empty` intent stops further recovery-worker starts
and permits subsequent backups under the existing bounded backup policy.
This action does not finish recovery of a previously funded wallet.

## Bounded on-chain pilot (0.1.0:6)

Before live funding, run `tests/test_wallet_actions.py` and the packaged regtest:

```sh
bash scripts/test-image-recovery.sh xbt-cln:recovery-test ../bitcoind --wallet-actions
```

Use Actions → **XBT Deposit Address** after recovery is finished and node health
is green. Each invocation generates a fresh address. Earlier addresses remain valid.
Address generation does not change the existing bounded-backup limits. Send a small XBT deposit,
for example 20,000 sats, and keep the total wallet balance at or below 100,000
sats. XBT and BTC share address prefixes: use the XBT chain, not BTC.

1. Use **Confirmed Wallet Funds** and wait for confirmation.
2. Generate a return address in your external XBT wallet.
3. Use **Prepare Test Withdrawal** with that address, an explicit fee rate
   (default 2 sat/vbyte) and total fee cap (default 2,000 sats). This reserves
   inputs and returns the entire confirmed on-chain balance minus the fee.
4. Review the destination, recipient amount and exact fee. Nothing has been
   broadcast. Keep the service running between preparation and submission.
5. Use **Send Prepared Withdrawal**, paste the review code and confirm review.
6. Use **Withdrawal Status** until confirmed; verify receipt in the other wallet.

**Cancel Prepared Withdrawal** discards a still-prepared transaction. This first
pilot retains one withdrawal record, including after cancellation or confirmation.
It does not create a second withdrawal. Repeating preparation with the same inputs
returns status; a different request is refused. No automatic resubmission occurs.
The review transaction and private destination remain in the local volume.

Requires no channels, one to ten confirmed native SegWit wallet outputs, and no
reserved, immature or unconfirmed outputs. A lost reply, service restart between
prepare/send, or validation failure can require local inspection: retain the
record and do not use another withdrawal command blindly. The CLN prepared
transaction is held in plugin memory and does not survive a node restart.

The helper persists `preparing`, `submitting` or `cancelling` before each mutation.
It verifies exact transaction inputs, the single destination output and integer
fee before submission. A tracked but unconfirmed transaction does not prove an
uncertain submission succeeded. Status reconciles a confirmed transaction without
resending. No PSBT conversion is required. The explicit fee works around the
previous fixture's relay-fee underestimate; it does not fix that upstream issue.

## Private-channel pilot (0.1.0:7)

Run the packaged disposable test before live funding:

```sh
.venv/bin/python tests/test_channel_actions.py -v
bash scripts/test-image-recovery.sh xbt-cln:recovery-test ../bitcoind --channel-actions
```

The pilot permits **one** private channel, 20,000–80,000 XBT sats, with no upper
wallet-balance limit for channel funding. The channel amount remains capped at
80,000 sats and the funding fee rate at 10 sat/vbyte, using at most ten inputs.
The 10,000-sat headroom is a funds requirement, not an absolute fee cap. Excess
input value returns as change. The separate on-chain sweep action retains its
100,000-sat cap. Use a peer you control for
the initial test. Peer identity and host stay local; status omits channel and
transaction IDs. Lightning invoice and payment actions are described below.

1. Obtain the other XBT node's public key, reachable IP/DNS host and Lightning
   port. Use **Connect XBT Peer**. This alone does not fund anything.
2. Complete any prior wallet withdrawal and check its status is confirmed.
3. Have at least 60,000 XBT sats for a default 50,000-sat channel. Wait for confirmed
   unreserved funds. All outputs must be confirmed and unreserved; at most ten
   inputs are supported. At least 10,000 sats above the channel amount are
   required for fees/reserves; CLN can enforce a larger reserve.
4. Use **Open Private Test Channel**, verify the peer and amount, choose an
   explicit funding fee rate (default 2 sat/vbyte), and confirm. This broadcasts
   funding, sets `announce=false`, and gifts no balance to the peer. Funding
   fees are additional; the fee-rate control is not an exact total-fee quote.
5. Check **Channel Status** until `CHANNELD_NORMAL` and connected.
6. When finished testing, copy the close review code from Channel Status and
   use **Cooperatively Close Test Channel**. It requires a normal connected
   channel with no pending HTLCs and targets the exact saved channel.
7. Wait for `close-confirmed`, then check Confirmed Wallet Funds.

Funding intent is saved before the funding RPC. Repetition only reconciles the
original attempt. A lost reply is matched against the peer, amount, privacy,
local opener, funding outpoint and exact wallet inputs. A missing or ambiguous
attempt remains for local inspection; it never creates a second channel.
The same stable lock serializes channel funding with wallet actions.

Close intent is also saved before RPC submission. The RPC uses
`unilateraltimeout=0`: no automatic timeout-triggered force close. Peer
misbehavior or other CLN conditions can still cause unilateral closure.
Cooperative close uses the configured funding fee rate as its requested fee
range. Repeats do not issue another close; an uncertain close result requires
inspection if no confirmed closing transaction was recorded.

Both pilots retain their attempt records. The existing one-shot withdrawal
pilot is not reset by closing a channel. Do not delete these records to bypass
an uncertain outcome. Tor, public announcements, larger balances and swap
coordinator services remain separate development steps.

## Lightning invoice and payment actions (0.1.0:10)

Create XBT Invoice accepts 1–10,000 sats and a unique label. It expires after one
hour; repeating that label returns the original invoice, including after a lost
reply. Use XBT Invoice Status to check receipt. A new invoice needs a new label.

Review Lightning Payment saves a fixed-amount XBT BOLT11 invoice and a routing
fee cap of 0–100 sats. Review the destination, amount and fee; retain the payment
reference and review code. Pay Reviewed Lightning Invoice requires that code
and explicit confirmation. CLN may try routes for 30 seconds, with a 144-block
maximum delay. This pilot does not support amountless or description-hash invoices.

The helper saves submission before calling pay. Repeated payment actions only
query CLN, even after failure or a lost reply. Missing payment records remain
unknown; never delete the saved record to retry. Payment Status checks the
original invoice, label, destination, amount, fee cap and preimage for completion.
Reviews are stored per payment hash, so separate invoices can be paid separately.
Do not concurrently pay the same invoice using another tool. These actions need
channel liquidity and do not open channels or perform swaps.

The underlying backup restrictions are unchanged: these are experimental pilots,
and backup is not a mechanism for resuming live channels after rollback.

## Starting another channel (0.1.0:11)

After a cooperative close, wait for Channel Status to report close-confirmed
and for the returned wallet output to be confirmed and unreserved. Use Archive
Confirmed Channel Close with its close review code. This preserves the original
record and returns a Next channel code; it does not submit a transaction.

Open Private Test Channel accepts that code in Previous close code, together
with the new peer, amount, fee rate and explicit funding confirmation. Leave
this field blank only for the first channel. Old funding requests cannot reopen
a channel. Opening is still limited to one active pilot channel at a time.

Archives retain the exact funding and close identities. The close must currently
be confirmed and spend the pinned funding output. Unrecognized historical
channels, pending HTLCs, unresolved closes, and archive mismatches block a new
attempt. Do not delete records to work around these checks. Lost close replies
without a saved close transaction still require local inspection.


## Coordinator setup and grants

Existing paired installations can keep their saved setup after this update.
For a fresh coordinator, use **Swap Setup → Coordinator Readiness**, then
**Prepare Coordinator** with explicit confirmation. Preparation checks identity,
chain synchronization, recovery state and pending HTLCs; it grants no payment
authority. Use **Create or Show Read-only Controller Credential** to obtain the
restricted monitoring rune for **Pair Coordinator Nodes** in Swap Controller.
Use that node's verified HTTPS interface and authenticated StartOS root CA.

Create or retrieve the node's separate **Inspection Credential** under
**Swap Setup**, then save both node inspection credentials in the controller.
These allow invoice, reserve and channel checks without payment authority.
Keep them private. Do not substitute an administrator rune, delete interrupted
credential records, or bypass a restore barrier.

Enable the bounded swap gate when the setup action requests it. On the XBT
coordinator, reverse swaps require **Enable Bounded XBT Swap Gate**, followed by
a restart if indicated and **XBT Swap Gate Status**. The BTC grant setup reports
any required BTC gate restart. Gate activation alone does not authorize a swap.
Grant controls under **Swap Grants** separately approve the fixed amounts,
route limits, selected channels and enrollment budget. Review those bounds
before confirming, then pair the credentials for that direction in the controller.

For routed BTC to XBT grants, explicitly enable **Allow routed swaps** and leave
the optional channel field empty to approve all currently eligible local channels
(up to eight). Existing direct grants keep their mode unless explicitly replaced.
XBT to BTC grants automatically select eligible local channels. New reverse
grants allow up to 288 BTC route-delay blocks; old grants retain 80 or 144.
A status check never renews or widens a grant.

After adding or closing channels, finish existing swaps before explicitly
replacing grants and pairing the new credentials. More receiving liquidity does
not resolve a fee/dust protection refusal. Preserve records if the outcome of
any earlier payment or grant operation is uncertain.

Development fixtures and historical release details are documented in README.md.

## Recipient hints and preparation errors

A recipient invoice needs a route the paying coordinator can discover. Private
hints being enabled does not guarantee a hint was included: CLN can omit a
channel whose peer appears to be a dead end. If preparation reports an unavailable
coordinator request while Swap Status says ready, check the recipient invoice's
actual hint count and channel readiness. A read-only route/history diagnostic
can distinguish a route refusal from an authority or transport problem. Keep
existing grants and records while diagnosing.

On a customer CLN node, explicitly selecting eligible local channels in the
invoice's exposeprivatechannels array can provide hints omitted by the boolean
setting. Select from current connected, normal channels with sufficient receiving
liquidity and verify that the new invoice contains a hint; never invent a SCID.
This does not widen grant authority or route limits. The forward preparation UI
can still mask a specific route refusal as a generic coordinator-request error.
