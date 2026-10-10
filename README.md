# XBT Core Lightning for StartOS

## Forward error reporting checkpoint (0063)

The user reported 0062 READY on 2026-10-09 (America/Vancouver): both four-case
funded regtest matrices and all three installer builds passed. Build versions:
BTC 26.6.9:8, XBT 0.1.0:26 and Swap Controller 0.1.0:23. After the installation
step, user-supplied read-only status confirmed ready pairing, saved inspection
credentials, a fresh worker, no backup pause and ready coordinator gates.

Initially both forward grants had expired with eight unused slots each; reverse
grants remained ready with three slots. The operator explicitly replaced and
paired only the forward grants. At checked_at 1791591029, both directions were
ready_to_prepare with no blockers, no active swaps and no records requiring
attention: ten forward slots per coordinator, three reverse slots. Forward
caps remained 80 blocks, four hops and 10,000 XBT msat; reverse caps remained
288 blocks, four hops and 10,000 BTC msat. The existing restore barrier remained
present. Readiness does not establish a route or constitute payment authority.
No new live swap, live route refusal, live restart or on-chain recovery result
was requested or reported for this update; prior live evidence remains below.

The UI summary did not make the individual grant reasons easy to locate during
this review; the packaged read-only CLI identified grant_expired on both nodes.
The Connection Status field live_payment_enabled=false describes that read-only
probe, not the separate swap grants. These presentation issues remain follow-up
work; no UI or runtime change is introduced by this checkpoint.

0063 changes seven documentation files only and exports the complete 0062 delta
from the synced swap-interface-live-20261009 tag with the exact tested installer
hashes. Keep those installers; no rebuild is required. Export on the packaging
VM, commit/tag/push on the tower, then retain VM stashes and fast-forward from
GitHub. The checkpoint scripts do not access live grants or payment records.

## Forward planning error fix (0062)

Candidate versions: BTC 26.6.9:8, XBT 0.1.0:26, Swap Controller 0.1.0:23.
The 0061 checkpoint was committed/pushed from the tower and synced on the
packaging VM, with stashes retained (user confirmation, 2026-10-09).
Apply against tag `swap-interface-live-20261009`; continue building/exporting
on the VM and committing/pushing on the tower.

Forward `plan` responses now carry only four fixed refusal codes: no bounded
route, route outside the grant, planning refused, or invalid recipient invoice.
The controller accepts only an exact one-field response during `plan`, and the
preparation action explains the applicable XBT fee, delay and hop limits. It
suggests private routing hints when the recipient has a private channel, without
claiming hints are missing or guaranteeing that they make a route possible.
Transport failures, malformed/unknown replies and all mutation errors remain
opaque. An older node still produces the generic uncertainty message until it
is updated. Reverse error behavior is retained.

This changes error reporting only: route selection, approved channel pins,
fee/delay/hop caps, one part/attempt, grant budgets, confirmation, invoice
publication, payment and restart recovery retain their existing rules. No state
migration or grant renewal is required. Refused preparation neither enrolls a
swap nor reserves a slot. Swap Status still checks setup rather than routes.
The earlier forward UI limitation described below applies to the 0061 release.
The subsequent user-reported funded build and post-update readiness checks
are recorded in the 0063 checkpoint above.

## Installed interface checkpoint (0061)

The user reported 0060 READY on 2026-10-09: operator/status checks, both four-case
funded matrices and all three installers passed. The packages were installed
and the cleaned menus appeared correct. Versions remain BTC 26.6.9:7,
XBT 0.1.0:25 and Swap Controller 0.1.0:22. 0061 changes documentation only;
its source export checkpoints the full 0060 implementation without rebuilding.

Live retesting: the user confirmed the forward customer XBT invoice was paid.
That test requested 1,000 BTC sats -> 2,000 XBT sats. The final received-amount
field and forward controller terminal status were not separately pasted for
this retest. The reverse test requested 3,000 XBT sats -> 1,500 BTC sats; the
user reported customer payment complete, controller settled and receipt in LND.
Final routes, fees, adjacency and payment timestamps were not supplied for these
retests. These are user-reported happy paths; no new live failure, restart or
on-chain recovery claim is made. Earlier 0059 evidence remains recorded below.

The first forward recipient invoice had zero hints despite requesting private
hints. Read-only coordinator diagnosis passed history checks and refused route
planning with bounded_route_unavailable (2,000,000 msat, final CLTV 40, 6,763
seconds remaining). A replacement invoice explicitly selected eligible local
channel hints on the customer VM, without manual SCID entry, and payment then
worked. CLN can filter dead-end peers even when exposeprivatechannels=true;
this is a possible explanation, not a separately observed warning in this run.

Known UI limitation: forward node-side planning refusals still cross the plugin
boundary as an opaque error. The controller can therefore show a generic
coordinator-request error for a missing bounded route. Reverse planning already
has a fixed, privacy-safe refusal protocol. A follow-up should extend that
protocol to forward planning while keeping mutation/unknown errors private.
Swap Status intentionally checks grants/setup, not invoice-specific routes.

Export source and installer copies from the packaging VM; commit/tag/push on the
tower; then retain VM stashes and fast-forward from GitHub. Do not pop retained
stashes onto an already-applied checkpoint. Service backups remain separate.

## Operator interface cleanup (0060)

Candidate versions: BTC 26.6.9:7, XBT 0.1.0:25 and Swap Controller 0.1.0:22.
0059 was committed/pushed from the tower and the packaging VM was synced, with
stashes retained (user confirmation, 2026-10-09). Apply 0060 against that exact
checkpoint tree. Build/test on the VM, export to the tower for commits/pushes,
then retain a VM stash and fast-forward from GitHub as before.

The controller normally presents 15 actions, grouped into Swaps, Swap Setup,
Status and Advanced / Recovery. Both directions have explicit preparation,
confirmation, history and draft-cancellation names. Setup credentials and grant
pairing are grouped together. Legacy quote/record inspection is shown only when
records exist (or cannot be inspected). An existing single pilot keeps its
approval and status actions. Old preparation, readiness, policy, gate-observer
pairing and regtest commands remain registered with hidden menu visibility;
visibility is not an authorization boundary. Their handlers and test entry
points retain all existing authorization and regtest guards.

Swap Status reads connections, the worker heartbeat, inspection binding and each
saved grant through its info operation. It reports remaining slots, enrollment
expiry, pause/replacement/exhaustion, exact direct/routed fee/hop/timing limits
and blockers for new preparation. It never plans a route, enrolls, advances,
renews, publishes or pays. Expired/paused grants remain inspectable. Responses
are bound to the saved session, node identity, network, pairing and restore
epoch; changed or stale observations are discarded. Output uses fixed fields
and reason codes, never endpoints, runes, certificates, invoices or raw RPC text.
The existing read-only pairing client gains no write methods. No report is
payment authority, and recipient-specific route/liquidity checks still happen
when preparing a swap. Existing enrolled recovery is unaffected by the report.

The coordinator grant controls are named by direction under Swap Grants, with
preparation and credentials under Swap Setup. Single-pilot authorization stays
under Advanced / Legacy so an older reviewed contract can still be authorized.
The old standalone gate-observer credential menu is hidden. Current inspection
credentials, grant retrieval, direct mode and all wallet/channel actions remain.

Known reserve, inspection, stale-worker, changed-channel, expired-review and
uncertain-request failures now have specific explanations. Unknown errors still
withhold private details. Existing internal pilot module names, journal paths,
contract profiles and action IDs are retained. No records, grants, restoration
barriers, payment algorithms or approval defaults are migrated. New swaps still
use one part and one outgoing attempt, with the same fixed prices and bounds.

## Live bidirectional checkpoint (0059)

On 2026-10-09 the user confirmed a live XBT → BTC swap: the customer XBT
payment completed, Reverse Swap History showed settled, and the LND recipient
invoice was SETTLED with 1,500 sats received. This follows the live BTC → XBT
result: 2,000,000 XBT msat received at 2026-10-09T01:41:09Z, controller settled,
and the LND payer reached the coordinator through an independent public peer.
These are user-reported live happy-path results, without independent node access.
The earlier reverse read-only route candidate was three hops, 200 blocks and
2,002 msat; the final executed route was not separately supplied. The reverse
XBT payer's adjacency was not reconfirmed. Live failure, restart and on-chain
recovery success have not been demonstrated by these results.

The packaging VM reported 0058 READY: all four reverse and all four forward
funded scenarios passed, and all three installers were built. The seven-node
reverse fixture covers non-neighbor customers, a 200-block public BTC prefix
plus private tail, seven balance changes, exact incoming binding, one outgoing
attempt, definitive failure, lost replies and pending coordinator restarts.
Local validation passed 103 focused Python cases and all three package checks.
These recovery results are regtest evidence, separate from the live settlements.

Installed versions remain BTC 26.6.9:6, XBT 0.1.0:24 and controller 0.1.0:21.
0059 changes documentation only; its cumulative export includes 0056–0058.
Export verified source and installer copies from the packaging VM, commit/push
on the tower, then retain VM stashes and fast-forward from GitHub. Do not pop
those stashes onto the already-applied checkpoint. The source checkpoint does
not replace runtime service backups or change existing grants.

## Reverse public-prefix timing update (0058)

0057 reached READY on the packaging VM: both funded matrices passed and all
three installers were built (user log, 2026-10-09). Its two-hop BTC fixture
covered only a 120-block private tail. The subsequent live read-only diagnostic
confirmed an active 144-block grant and found the complete three-hop route at
200 blocks and 2,002 msat. Increasing only the fee budget did not find a route
at 144. The later 0058 live settlement is recorded above.

New explicitly requested grants use `startos-reverse-repeat-v3`, with a
288-block total BTC route cap; their contracts use `startos-reverse-routed-v3`.
This accommodates three 80-block forwarding deltas plus the fixed 40-block
recipient delay in a four-hop route (280 total). This is a cap, not a promise
that arbitrary routes fit. The fee cap stays 10,000 msat, with at most four hops,
one part and one outgoing attempt. Recipient invoices still require final CLTV
at most 40 and at least 33 minutes remaining.

Existing v1/v2 grants and contracts retain 80/144 blocks. Retrieval never widens
a grant; installation rewrites no authority or journal. The default local enable
API still requests 80, while the explicit StartOS action requests 288. Both
coordinators enforce the contract profile against the stored grant before
reserving a slot. Paired limits must match. Unfinished swaps block renewal;
paused or expired enrolled swaps retain their original recovery authority.

Incoming timing derives from the exact saved outgoing route: BTC delay + 6
submission blocks + 144 XBT recovery blocks, plus 24 quote-drift blocks in the
invoice. A 200-block route requires 350 blocks before submission and advertises
374. The incoming close guard remains 144 blocks. Existing contracts recover
without replanning, changing bindings or repeating mutations. The relative-chain
progress assumptions of the existing policy are unchanged.

Route refusal now names the actual paired cap (80, 144 or 288). This value comes
from the validated grant profile. Only fixed safe reason codes reach the UI;
raw RPC text, invoice data and credentials remain private. Forward/direct flows
and their grant namespace are unchanged.

Verified versions: BTC 26.6.9:6, XBT 0.1.0:24, controller 0.1.0:21. The VM
rebuilt all three images, passed both funded matrices and built the installers.
The reverse fixture has seven nodes:
three on XBT and four on BTC, with two public BTC channels and a private final
channel. Both BTC forwarding nodes advertise 80 blocks, 1,000 msat base and
1 ppm; the fixture requires 200 blocks, 2,002 msat, all seven balance changes,
actual incoming binding and one outgoing attempt. The process preflight covers
the same route for settlement, lost replies, failure and restart. Local tests
simulate CLN/transport; the native funded and installer checks ran on the VM.

## Historical reverse implementation and validation (0056–0056c)

Adds a separate XBT → BTC repeat flow at a fixed test price: 3,000 XBT sats in,
1,500 BTC sats delivered. At 0056 this was a candidate pending the VM funded
matrix; the current funded and live outcomes are recorded above. The forward live checkpoint is
retained: BTC `1211fcd`, XBT `50635bb`, controller `910fc28`.

Reverse credentials use only `swap-reverse-call`, with a named session ID and
exactly five parameters. They cannot call raw payment/close methods or the
forward authority method. Forward credentials cannot authorize BTC spending.
Reverse session and swap records use separate `reverse-sessions` and
`reverse-swaps` directories; grants last 24 hours and consume 1–10 durable slots.
Recovery rights for an enrolled swap survive expiry, pause and renewal. New
admission checks unresolved records in both directions under the common lock.
Restores block old authority; backups omit credentials and executable records.

The signed BTC recipient invoice determines one immutable route: at most four
hops, 10,000 msat BTC fee, 80 blocks first-hop delay and 40 blocks final delay.
The incoming XBT invoice advertises approved channels using the peer's remote
alias where required. The actual committed incoming HTLC/funding pin is persisted
before BTC submission. There is one part and one outgoing attempt, with no
payment retry after a missing reply. The actual outgoing BTC HTLC ID and expiry
are also persisted when observed; route planning is never repeated during recovery.

Reverse timing uses the existing candidate budget: BTC route delay + 6 blocks
submission slack + 144 XBT blocks recovery reserve; the invoice adds 24 blocks
quote drift. Independent chains do not guarantee relative progress. At 144 XBT
blocks remaining an unresolved attempt requests protection of the original
incoming channel exactly once. Expiry alone never authorizes failure or resend.
Post-close status remains on-chain recovery, not verified settlement.

The XBT extension retains the pinned reverse gate's existing activation, journal,
and older quote profiles. `reverse-repeat-register` validates the new exact
contract, while `reverse-retire-repeat` permanently expires an unpaid quote.
An accepted replay can only resolve its original binding. The shared anchor
fee/dust check and actual untrimmed-HTLC checks remain in force.

Packaging workflow: apply/build/test on the packaging VM, export verified source
to the tower, commit/push there, then stash and fast-forward the VM. Never pop
checkpoint stashes onto already-applied source. This candidate makes no commits,
pushes, live activations or live payments automatically.


Experimental fresh-wallet on-chain pilot package for StartOS 0.4, forked from
Start9Labs/cln-startos at `6040fb4a8cfdaaa9ef8cd468e60c2e14a028c928`.

**Do not migrate existing wallets.** Version 0.1.0:6 adds a bounded on-chain
pilot (at most 100,000 sats total) after empty-wallet recovery validation.
Run the packaged wallet-action regtest before a small live deposit.

## Identity and source

- Package: `xbt-cln`, wrapper version `0.1.0:11`.
- Wrapper: https://github.com/BitcoinMechanic/xbt-cln-startos
- Node: https://github.com/BitcoinMechanic/lightning
- Pinned node commit: `81ba4099a63e5a0e83f55cead53c54f2a1b3c1fe`.
- Binary version: `xbt-81ba4099a63e`.
- Image definition: `Dockerfile.xbt`; source/contract record: `assets/xbt/source-lock.json`.

Source is pinned; apt packages and base image tags are not a claim of bit-for-bit
reproducibility. The inherited `Dockerfile` and unregistered legacy action/config
sources remain as porting references. They are not the active XBT runtime.
The original CLBOSS and TEOS submodule pins remain unchanged.

## Runtime and backend contract

The sole `main` volume mounts at `/root/.lightning`; CLN's XBT wallet lives in its
`xbt/` subdirectory. CLI calls explicitly select `--network=xbt`.
`--conf=/dev/null` prevents inherited Bitcoin/plugin settings from being loaded.
The peer interface (TCP 9735), Node Info, recovery actions and bounded on-chain
wallet and private-channel actions are registered.
No web UI, remote wallet RPC interface, swap role, CLBOSS, Sling, watchtower,
custom VPN, or automatic public address announcement is enabled in this stage.
Start Tunnel and Tor operation will be validated separately.

The local backend dependency still has ID `bitcoind`, with host `rpc`, internal
port 8332, volume `main`, and cookie at its root. This matches Retropex/knots-startos
commit `813da42c9308e027f0c193e650142bcf37b2cd62` (`#knots:29.4.2:3`).
The bitcoin-core-startos TypeScript dependency supplies the structurally identical
mount type and RPC constants; it does not establish the backend's chain identity.

Before starting lightningd, an RPC preflight requires synced, unpruned mainnet,
active BLAKE2b at height 961640, and the pinned block hash
`0000000000000050c1e5f69672f459293be14f46e5a494e7a8c8541396f18eeb`.
The fork's bcli plugin independently enforces XBT identity during operation.
Backend credentials come from a read-only cookie mount, never from package inputs.
Cookie replacement triggers reconfiguration; temporary disappearance does not.

## Bounded backup and force-close recovery

Version 0.1.0:2 wires `assets/xbt/recovery.py` into the stopped-service backup
and fresh-volume restore hooks. SQLite/WAL/SHM, RPC sockets and gossip remain
excluded. The receipt binds the XBT node identity, key, encrypted SCB and expected
channel IDs. This is an integrity check, not authentication of a malicious backup.
Older empty-wallet receipts from 0.1.0:1 remain supported.

The initial profile allows at most eight normal channels, no pending HTLCs,
no inflight funding, no reserved or unconfirmed wallet outputs, and wallet
address counters at most 50. Other states are refused rather than silently
claiming coverage. Capture during unfinished recovery is refused. Finished empty-wallet recovery
permits subsequent bounded backups. Historical
settled HTLC rows are allowed. These restrictions bound the tested recovery path;
they are not a general CLN backup policy.

Restore writes a blocking marker before validation. It refuses an existing wallet
database, verifies key/SCB bindings and writes a durable recovery intent. Startup uses a fresh database and the saved absolute scan height. Old backups
without a saved height default to block one. Once RPC reports no sync warnings, the recovery worker checks
identity and backed-up channel IDs, then invokes `emergencyrecover`. CLN asks peers
to force-close. It does not resume old channels or restore an old database.

An interrupted import is reconciled against channels already in the fresh DB.
An imported marker prevents re-import after a resolved channel disappears.
The recovery health check stays pending for peer closure and on-chain processing;
it never equates ONCHAIN or an empty channel list with proven fund recovery.
A stale status or worker failure is not green health. Keep the backup throughout.
Funded recovery completion needs manual output/funds verification. Only
never-funded recovery has a completion action. An unavailable peer may delay recovery indefinitely.

The wrapper has no general wallet UI or wallet migration. Do not run the original and
restored wallet concurrently. The packaged regtest uses disposable keys and a
surviving peer; it now invokes the same capture, restore and recovery-step code
used by StartOS, including a repeat step. StartOS lifecycle execution still needs
separate validation. The default regtest withdrawal underestimated relay fees;
the fixture uses an explicit 2000perkb fee while that separate issue is unresolved.

## Local validation

```sh
npm ci --ignore-scripts
npm run check
npm run test:xbt
python3 -m venv .venv
.venv/bin/python tests/test_empty_backup.py -v
.venv/bin/python tests/test_recovery.py -v
npm run build
npm run check:bundle
```

The policy checks are offline. The bundle check verifies the exported package ID,
version, image, dependency and action set. They do not emulate StartOS.

Build the source image on the amd64 tower (explicit TARGETARCH also works with the
legacy Docker builder):

```sh
docker build -f Dockerfile.xbt --build-arg TARGETARCH=amd64 \
  --build-arg BUILD_JOBS=28 --build-arg RUST_BUILD_JOBS=4 \
  -t xbt-cln:81ba4099a63e .
docker run --rm --network none xbt-cln:81ba4099a63e xbt-image-check
```

The source image and four native self-tests passed on the tower, and version
0.1.0:0 started and retained its identity across service restarts on StartOS.
This update adds one Python file to the runtime image, reusing the expensive
compile layers. Build the package in the VM with:

```sh
BUILDX_BUILDER=startos-builder make x86
```

The empty-wallet StartOS backup/restore round-trip passed with the same node ID.
The nine offline backup tests use synthetic SQLite fixtures; they do not claim
real channel recovery coverage.

## Packaged-image channel recovery fixture

The empty-wallet StartOS backup/restore round-trip passed with the same node ID.
`tests/image_recovery.py` now exercises a separate funded **regtest** wallet in
an isolated Docker container. It opens a channel, pays, cleanly stops the owner,
copies only `hsm_secret` and `emergency.recover` to a fresh directory, and asks
the surviving peer to close. Success requires spending a confirmed recovered
channel output into the peer's wallet. The original database is retained only
as a diagnostic artifact and is never copied into the recovered node.

Use the already-built package image and your BLAKE2b Knots executable:

```sh
docker image ls start9/xbt-cln/lightning
bash scripts/test-image-recovery.sh IMAGE_ID ../bitcoind
```

This does not rebuild the package. The launcher publishes no ports and uses
`--network none`; backend and Lightning traffic stays on container loopback.
Only the executable, test script and a newly created temporary results directory
are mounted. Logs and disposable regtest keys remain in that results directory.
The executable must run on Debian bookworm, the image's runtime base.

This fixture calls the hook helpers but does not emulate StartOS lifecycle, test
an offline surviving peer, or cover unresolved HTLCs. Live on-chain testing
is bounded separately below.


## Recovery scan start (0.1.0:3)

Before creating a brand-new key/database, backend preflight records a starting
height 144 blocks behind the verified tip in `wallet-birth.json`. Existing wallets
or restored identities do not get an inferred birthday. Capture includes that
height in its receipt; old receipts default to 1. This is an optimization for keys
created by this package, not a claim that all imported keys are new.

For a legacy restore of a wallet the operator knows has NEVER been funded, the
stopped-service **Set Empty-Wallet Recovery Scan Start** action accepts a positive
height safely before wallet creation and explicit confirmation. It refuses an
imported recovery, any expected channels, or recorded activity in the fresh
restored database. Database bytes and backup files are preserved. Startup refuses
a selected height above the verified backend tip. Do not use the action to skip
history for a funded wallet; an empty restored database is not proof of no funds.

Recovery health displays the scan starting height and current CLN block height.
The worker still never declares completion automatically. SQLite test fixtures
now close their connections explicitly (including on Python 3.13).

```sh
.venv/bin/python tests/test_recovery.py -v
.venv/bin/python tests/test_empty_backup.py -v
bash scripts/test-image-recovery.sh xbt-cln:recovery-test ../bitcoind --empty-scan
```

The added Docker mode stops an empty restored node during an early scan, advances
its configured scan start to 1900, restarts the same database and verifies sync to
2000, unchanged identity and pending manual-review status. No database is deleted.


## Recovery daemon registration fix (0.1.0:4)

The SDK daemon builder is immutable. Versions 0.1.0:2 and 0.1.0:3 discarded the
return value when adding the conditional recovery daemon, so CLN started and
scanned but the worker and its health check were absent. Version 0.1.0:4 returns
the extended chain. Existing intent and scan-start records are preserved.
`scripts/test-recovery-topology.cjs` executes the wrapper factory against the
actual SDK builder, mocking only files, container access and backend discovery.
It asserts the recovery daemon is present for prepared/importing/imported states,
waits for lightningd, and reports pending or attention rather than completed
recovery. The test fails with the original registration bug and runs under
`npm run test:xbt`. This is not an emulation of the StartOS UI.

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

### Grant renewal after a completed swap channel closes

A routed grant snapshots its channel pins when created. Supplying a short channel
ID restricts that snapshot to that channel; leaving the field empty includes up
to eight currently normal, connected, idle local channels. Adding or closing
channels does not modify an existing grant. Finish current swaps, explicitly
replace the affected coordinator grant, and pair the replacement credential.

Historical completion no longer requires the original channel to remain normal.
The node still checks the saved contract, outcome, exact funding pin and incoming
HTLC binding. For retained non-normal channels it additionally verifies the
original HTLC's terminal wallet state using local `listhtlcs`; missing or
ambiguous evidence blocks renewal. Once CLN archives a fully resolved channel,
`listclosedchannels` must match every original pin field. Original journals are
never rebound or cleared. A recorded deadline close, unresolved outcome, changed
binding/funding, or restore barrier still blocks renewal. These local reads do
not expand remote rune permissions. Unpaid retirement must remain unbound.
