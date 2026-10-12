# XBT Core Lightning

This migration candidate adds a wallet and channel dashboard to the XBT node. It requires synced, unpruned BLAKE2b Knots. It is not yet an update for your installed experimental XBT node.

The dashboard supports XBT wallet addresses, channels, BOLT11 invoices and payments. Set its own password on first use. XBT units and explorer links are explicit; fiat estimates are unavailable. BTC invoices are refused before payment. BOLT12 offers, external watchtowers and automatic rebalancing are not enabled in this candidate.

The node verifies the BLAKE2b backend before creating or opening its wallet. Internally the fork still calls its network and wallet directory `bitcoin`; that name does not mean it is following BTC.

Backups preserve keys and emergency channel recovery data, not a copy of the live channel database. A restored node attempts recovery, asks for a rescan and remains marked as restored. Recover and drain funds before starting fresh. The recovery test must pass before release; actual StartOS backup/restore also remains to be validated. Recovery depends on peers cooperating, and the automatic address window is bounded.

Your existing swap controller and nodes remain in use. The migrated swap modules are bundled but not activated by this package. Do not import an existing experimental XBT wallet or channel directory into it.

Use the supplied 0088b recovery test on the packaging VM after checkpoint 0087 is synced. It retains the validated UI and fixes fee estimation when withdrawing recovered channel funds and tests disposable regtest recovery, without creating an installer or touching installed services.
