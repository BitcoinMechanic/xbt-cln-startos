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

Backups preserve keys and emergency channel data, but restoration is not enabled:
a restored installation refuses to start. Do not delete the restore-blocked file.
Your existing tower nodes and customer VM are separate installations and remain
in use while this package is tested.
