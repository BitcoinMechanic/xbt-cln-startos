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

Backups with recorded wallet/channel activity are refused in this release.
Backups made by 0.1.0:0 lack the new receipt and cannot be used for this test.
A missing or changed key/recovery file blocks restoration. Keep both the original
and backup when any check fails; do not delete the restore-blocked marker.

This is not funded-wallet or channel recovery. Keep the node unfunded. Your tower
coordinators and customer VM continue to operate separately.

The development recovery test uses disposable regtest coins inside an isolated
Docker container. It is separate from StartOS backup/restore and does not enable
funded backups in this release. The empty-wallet restore has been verified to
retain the node ID; continue keeping this StartOS node unfunded.
