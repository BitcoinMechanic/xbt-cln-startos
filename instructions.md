# XBT Core Lightning — bounded on-chain pilot

This is an experimental XBT (BLAKE2b) Lightning node, distinct from Bitcoin Core
Lightning. It requires a synced, unpruned BLAKE2b Knots service on the same StartOS
box. A service called `bitcoind` is not sufficient: startup checks its chain.

Use a fresh installation. Do not import an existing node or open channels yet.
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
is green. The address is reused for this pilot. Send a small XBT deposit,
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
