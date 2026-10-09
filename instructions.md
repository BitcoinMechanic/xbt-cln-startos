# XBT Core Lightning — bounded on-chain pilot

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


## Coordinator preparation (0.1.0:12)

The default remains an ordinary XBT Lightning node. The image now includes the
swap modules from CLN commit `81ba4099a63e5a0e83f55cead53c54f2a1b3c1fe`
in an inert directory outside plugin discovery. No swap gate, controller,
quote API or network listener is started by this addition.

**Coordinator Readiness** checks the bundle, node identity, synchronization,
recovery state and absence of pending HTLCs. **Prepare Coordinator** requires
explicit confirmation and saves a local preparation receipt tied to this node,
network and source revision. Repeating preparation preserves the same receipt.
Neither action sends payments or changes channels. The readiness action only
reads node RPCs; its action lock may be created locally.

This is preparation only, not live swap authorization. A future controller
pairing step must bind both operators and their policy before enabling gates.
The receipt is not a substitute for that activation check, and is not included
in key/SCB recovery backups. Recovered nodes must be prepared and paired again.
Existing wallet and channel actions continue unchanged.


## Read-only controller credential (0.1.0:13)

Coordinator Preparation includes Controller Credential Status, Create or Show
Read-only Controller Credential, and Revoke Read-only Controller Credential.
Run Prepare Coordinator first. Creation/export requires the existing XBT
identity, synchronization and recovery checks to pass. The rune is masked and
copyable; status never returns it. It permits only `getinfo` and
`listpeerchannels`, with zero parameters. No payment methods are authorized.

Repeated creation returns the same active rune. A durable creation intent
prevents another mint after a lost reply; an interrupted creation requires
inspection, not deletion of its record. Revocation targets only the saved rune
ID and reconciles a lost reply. Repeated revocation is safe, and revoked runes
are not automatically replaced in this version.

The private controller-read-only.json record stays on the main volume and is
included in backups. Its saved phase is not proof of credential validity after
a database restore: the helper checks CLN's stored rune and blacklist before
export/status/revocation. Missing, changed or unexpectedly unrevoked credentials
are refused. Restored credentials require inspection; preserving CLN revocation
history through restoration is outside this patch's guarantees.

No REST listener or StartOS interface is added here. A later transport step
will pair the controller using verified HTTPS; never transmit this rune over
unencrypted HTTP. Existing peer connectivity remains as configured.

Validate on the packaging VM:

```sh
python3 tests/test_controller_credential.py -v
npm run check
npm run test:xbt
npm run build
npm run check:bundle
docker buildx build --builder startos-builder --load \
  -f Dockerfile.xbt -t xbt-cln:recovery-test .
bash scripts/test-image-recovery.sh \
  xbt-cln:recovery-test ../bitcoind --controller-credential
```

The disposable test uses real XBT regtest preparation and credentials, verified
HTTPS reads, server-side denial of newaddr, and repeated revocation. It neither
uses live wallets nor changes the installed StartOS package.


## Controller RPC interface (0.1.0:14)

The XBT Controller RPC interface exports CLN REST on internal port 3010,
with host/interface ID `controller-rpc`. It has no rune, username, or query
parameters in its URL. The Lightning peer interface retains its existing ID
and port. Use the HTTPS address shown by StartOS rather than assuming an
external port: StartOS may assign a different port when one is occupied.

StartOS terminates HTTPS at its edge and forwards HTTP to CLN REST inside
the service network. The SDK's HTTP binding uses `secure: null` and an
`addSsl` listener; the package does not mark plaintext as safe for untrusted
networks. Local/bridge HTTP may still be available to trusted paths. Use only
verified HTTPS for off-box controller credentials. Reachability and enabled
addresses remain under the operator's StartOS interface settings; this patch
does not configure Tor or public exposure.

CLN REST uses Rune authentication for RPC. The dedicated controller rune
restricts requests to getinfo and listpeerchannels without parameters. The
endpoint itself is not a read-only filter: another rune carries its own
permissions. Do not substitute an unrestricted rune. Public CLN REST metadata
or documentation routes are not proof of authenticated RPC access.

For an off-box client, obtain the server's root CA through the authenticated
StartOS certificate download flow and trust it explicitly when verifying the
HTTPS URL. This package's pinned SDK does not provide getRootCa, so no custom
certificate-export action is included. Do not disable certificate or hostname
verification to work around a connection failure.

```sh
npm run check
npm run test:xbt
npm run build
npm run check:bundle
BUILDX_BUILDER=startos-builder make x86
```

The interface test executes the factory with the installed SDK's real
MultiHost/Origin implementation and verifies the generated TLS binding and
credential-free URL. The daemon topology test verifies the matching CLN REST
port, host and HTTP protocol flags. These checks do not exercise a live StartOS
edge proxy: verify external HTTPS and denied unauthenticated RPC after updating.
Existing credential records are reused; no swap gate or controller is activated.

## XBT reverse gate opt-in and observation

XBT Core Lightning 0.1.0:15 adds **XBT Swap Gate Status** and
**Enable Bounded XBT Swap Gate**. Prepare Coordinator must already succeed,
and a connected normal channel with no pending HTLCs is required for activation.
Activation saves a receipt bound to this node, its wallet secret hash and the
exact pinned Python source bundle. Restart the service explicitly, then check
status again. The wrapper loads immutable image code; the durable gate journal
is stored at `xbt/swap-gate/reverse_gate.quotes.json`.

The reverse gate uses `reverse-live-v1`: 1,500 BTC sats payout, incoming XBT from
1 to 500,000 sats, at most 30 BTC sats routing fee, and one active quote at a time.
These are existing pilot bounds, not a market price or a controller authorization.
The forward BTC gate's `live-pilot-v1` limits are different. Ordinary payments
with unregistered hashes continue normally. This action publishes no invoice,
registers no quote, creates no credential and submits no payment.

Activation is excluded from backups. Restore writes a gate barrier before
removing activation and running existing recovery checks. The gate journal is
preserved; an existing journal without its activation cannot be silently reused.
There is no automatic barrier reset or gate-disable action for unresolved swaps.

After the gate is active, use **Create or Show XBT Gate Observation Credential**.
It permits only parameterless `getinfo` and `reverse-pilot-info`; its status and
revocation actions are separate from the existing monitor credential.
In Swap Controller 0.1.0:8, **Pair XBT Gate Observation** reuses the saved XBT
HTTPS endpoint and CA, verifies both node identities and binds the new credential
to the current pairing generation. Existing BTC gate pairing is preserved.
Controller backups omit both observation credentials and restore removes them.

Live Swap Readiness verifies the two profiles independently. XBT observation
reports `gate_active`, not a remote quote count (that RPC does not expose one).
Verifying both profiles removes only the gate-verification blocker: live
execution, execution credentials, amount/fee/expiry policy, cross-chain timing
and any restored execution barrier remain separate outstanding requirements.


## Dedicated swap inspection credential (0.1.0:16)

Use **Create or Show XBT Inspection Credential** under Coordinator
Preparation to mint or reveal the separate read-only preflight rune. Explicit
confirmation is required. Its exact method allowlist is `decode`, `getinfo`,
`listfunds`, `listpeerchannels`, and `listsendpays`; it has no payment, gate,
channel-management or credential-management authority. These reads expose
wallet, channel and payment history information, so keep the rune private.
The existing monitor and gate observer credentials retain their scopes.

Paste this masked rune only into the Swap Controller live inspection form.
Creation requires coordinator preparation but does not activate any gate.
Repeating creation returns the same active rune. Status never reveals it.
Revoke targets only this rune ID and derivatives. A lost creation reply leaves
a durable creating record and cannot automatically mint another rune. Revoked
or interrupted credentials require separate inspection, not file deletion.

The private receipt `controller-inspection-read-only.json` and lock are
excluded from backups; the receipt is removed on restore. This does not revoke
an externally retained rune on a still-running original node. Inspection grants
no execution authority, and existing gate restore barriers remain in effect.

## Explicit forward pilot authority

This candidate adds **Authorize XBT Forward Pilot**. It authorizes one immutable
contract prepared by Swap Controller 0.1.0:12: 1,000 BTC sats in and 2,000 XBT sats
out, using the existing direct channels. Installing this version does not grant
authority or start a payment. The image-owned pilot plugin remains inert until
this local action is explicitly confirmed.

Paste the complete reviewed contract JSON into the action. Confirm the node
identities, channel funding pins and recipient with the controller review, then
return the displayed pilot ID and masked rune to the controller. The rune only
permits `swap-pilot-observe` and `swap-pilot-step` for this exact contract. The
node-side implementation fixes the amounts, recipient, route, original payment
attempt and permitted channel/gate operations; it exposes no generic RPC proxy.
An XBT grant can spend the contract's 2,000 sats. A BTC grant can publish its
invoice, resolve its bound gate, or force-close its selected channel for deadline
protection. These are execution credentials, separate from inspection credentials.

There is one contract slot per node. Repeating authorization for the identical
contract returns the same credential; another contract is refused. An expired
or interrupted enrollment needs inspection, not deletion of the journal or
blind replacement. Unknown mutation replies are reconciled from original node
evidence; an intent without sufficient evidence blocks further submission.

The authority record is private and excluded from backups. Restore creates a
persistent pilot barrier, alongside the existing gate barrier. It cannot resume
old execution or be cleared by re-pairing. Keep both nodes and Swap Controller
running until completion. A forced close can cost more than the pilot amount.

Validation for this candidate includes local unit/action/build checks. Its new
funded pilot matrix must pass on the packaging VM before installation and live
approval. Regtest uses a fixture-only currency adapter; that adapter is never
included in service images and does not prove live-chain timing safety.

## Core Lightning 26.06.9 security update

This revision carries the upstream 26.06.9 security update, including channel
reestablishment, shutdown HTLC deadlines, splicing, onchaind, gossip throttling,
rune authorization and persistent configuration hardening. The BTC package
uses the signed release binaries. The XBT package retains its existing fork,
network identity and database lineage and builds with a checksum-pinned source
overlay of the 26.06.9 fixes; it is not a downgrade to the stable BTC binary.
Swap/gate Python source pins are unchanged. Existing channels use the same
persistent data. Do not replace XBT with an unmodified Bitcoin CLN package.

The CLBOSS Auto Close packaging fix is also included: its configuration is
written as `clboss-auto-close=true` rather than a bare flag. Existing values are
normalized by the regular config writer. Start SDK remains 2.0.9.

The security build must pass its image checks and the funded pilot matrix
before pilot approval. The customer VM's separate XBT daemon also needs the
updated XBT binary; updating the StartOS coordinator does not update that VM.

Upstream release: https://github.com/ElementsProject/lightning/releases/tag/v26.06.9
StartOS SDK-2 release: https://github.com/Start9Labs/cln-startos/releases/tag/v26.6.9_0

## Bounded repeat-swap grant

**Enable Repeat Swap Grant** creates a reusable controller credential pinned to one connected channel, for 1–10 fixed 1,000 BTC sat → 2,000 XBT sat enrollments (default 5). New enrollment expires after 24 hours. Copy this credential into the controller's **Pair Repeat Swap Grants** action once. Leave New grant off to retrieve the same credential without renewing its budget. Explicit replacement requires all previous enrollments to be terminal.

Each enrolled contract consumes a slot, including failed or expired swaps. **Pause New Swap Enrollments** stops new contracts while preserving recovery for already enrolled contracts. The credential cannot issue arbitrary node RPCs. Deadline protection can force-close the pinned BTC channel and incur on-chain fees. Restore barriers remain enforced.

The first pilot record and prior quote history are preserved. Repeat contracts have separate durable records; exact retries reuse their original slot. Restart the BTC coordinator after first enabling repeat mode if requested. The controller then offers invoice-only preparation, explicit confirmation, and swap history. Candidate funded regtests must pass before installation.


### Routed forward swap candidate

Enable Repeat Swap Grant now has an explicit **Allow routed swaps** option,
off by default. Existing direct grants keep their original scope. After all old
swaps finish, select New grant to change modes. An empty channel field in routed
mode snapshots up to eight currently connected, normal, idle local channels;
new channels are never added automatically. Grant expiry, slot consumption,
pause and restore barriers retain their previous behavior.

The fixed swap remains 1,000 BTC sats for 2,000 XBT sats. The XBT coordinator may
spend at most 10 additional XBT sats in routing fees, with a maximum of four hops
and 80 blocks total outgoing CLTV. The final hop receives exactly 2,000 sats with
40 blocks CLTV. There is one payment part and one outgoing attempt, with no
payment retry or replanning after approval. Only invoice-bound read-only planning
is added to the restricted session wrapper; no raw RPC authority is granted.

The BTC invoice advertises eligible approved receiving channels using the peer's
observed fee and CLTV policy. Private-channel route hints expose those channels
to the payer, who still needs a reachable path to a hinted peer. The accepted
incoming HTLC selects the actual approved channel. Its funding identity, HTLC ID
and expiry are durably recorded before outgoing submission; deadline protection
can close only that original channel. An unapproved channel or changed funding
blocks outgoing submission. Existing mutation intents remain observe-only after
an uncertain reply.

The route conversion helper is vendored unchanged from
`tools/blake2b/reverse_route.py` at source commit
`81ba4099a63e5a0e83f55cead53c54f2a1b3c1fe`. The new wrapper and contract validation
apply the fixed forward-swap limits independently. Public routes and bounded
BOLT11 route hints are supported; multipath, blinded routing, automatic retries
and reverse routed swaps are outside this candidate.

Local regression tests cover the new bindings and preserve direct repeat flows.
Funded six-node validation is provided by the controller's `--routed` harness;
its execution on the packaging VM is required before installing this candidate.


Private incoming BTC route hints follow CLN's SCID-alias rules: negotiated
alias channels require the peer's remote alias; a missing alias is not replaced
with the funding SCID. Legacy private channels prefer an available remote alias.
The approved funding pin and the actual incoming HTLC binding remain unchanged.
The funded routed fixture checks the advertised alias before paying and reports
the payer's error directly if it exits before the gate accepts its HTLC.

### After changing channels

Repeat grants keep the channel list approved at creation. If you entered a
channel short ID, only that channel was approved. After adding or closing a
channel, finish current swaps and run **Enable Repeat Swap Grant** on the
affected coordinator. Enable **Allow routed swaps**, leave the channel field
empty, choose the swap budget and enable **Replace a previous grant with a new
24-hour budget**. Authorize it, then use **Pair Repeat Swap Grants** in Swap
Controller with the new credential and the other coordinator's current grant.

A completed swap's closed channel can be checked against its retained history.
If that history is unavailable or the swap still needs recovery, renewal remains
blocked. Keep the swap records; opening another channel does not resolve an
unsettled swap.
