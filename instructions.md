# XBT Core Lightning — observation release

This is an experimental XBT (BLAKE2b) Lightning node, distinct from Bitcoin Core
Lightning. It requires a synced, unpruned BLAKE2b Knots service on the same StartOS
box. A service called `bitcoind` is not sufficient: startup checks its chain.

Use a fresh installation with no funds. Do not import your existing node, fund
the wallet, or open channels yet. This stage validates the package's connection
to Knots and its XBT node identity.

The **XBT Node** health check reports readiness. **Node Info** displays the node
ID and available peer addresses. There is no web wallet UI in this release.
The swap controller and coordinator roles are not installed by this package yet.

This release supports a backup/restore test of the empty observation wallet:

1. Upgrade to 0.1.0:1, start it, and privately record its Node Info ID.
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

Keep the node unfunded pending validation of the new recovery integration. Your tower
coordinators and customer VM continue to operate separately.

The development recovery test uses disposable regtest coins inside an isolated
Docker container. It validates recovery helper behavior separately from the StartOS lifecycle. The empty-wallet restore has been verified to
retain the node ID; continue keeping this StartOS node unfunded.


Version 0.1.0:2 adds experimental recovery orchestration. Continue using an
unfunded StartOS node while the integration is being validated. The Docker test
now exercises the same backup/restore helpers as the package.

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
