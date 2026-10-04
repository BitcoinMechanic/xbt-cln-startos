# XBT Core Lightning for StartOS

Experimental fresh-wallet on-chain pilot package for StartOS 0.4, forked from
Start9Labs/cln-startos at `6040fb4a8cfdaaa9ef8cd468e60c2e14a028c928`.

**Do not migrate existing wallets.** Version 0.1.0:6 adds a bounded on-chain
pilot (at most 100,000 sats total) after empty-wallet recovery validation.
Run the packaged wallet-action regtest before a small live deposit.

## Identity and source

- Package: `xbt-cln`, wrapper version `0.1.0:9`.
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
transaction IDs. There is no Lightning invoice/payment UI in this patch.

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
