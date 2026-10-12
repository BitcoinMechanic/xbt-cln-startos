# XBT Core Lightning

This migration candidate adds a wallet and channel dashboard to the XBT node. It requires synced, unpruned BLAKE2b Knots. It is not yet an update for your installed experimental XBT node.

The dashboard supports XBT wallet addresses, channels, BOLT11 invoices and payments. Set its own password on first use. XBT units and explorer links are explicit; fiat estimates are unavailable. BTC invoices are refused before payment. BOLT12 offers, external watchtowers and automatic rebalancing are not enabled in this candidate.

The node verifies the BLAKE2b backend before creating or opening its wallet. Internally the fork still calls its network and wallet directory `bitcoin`; that name does not mean it is following BTC.

Backups preserve keys and emergency channel recovery data, not a copy of the live channel database. A restored node attempts recovery, asks for a rescan and remains marked as restored. Recover and drain funds before starting fresh. Funded backup recovery still needs validation before release.

Your existing swap controller and nodes remain in use. The migrated swap modules are bundled but not activated by this package. Do not import an existing experimental XBT wallet or channel directory into it.

For now, use the supplied 0086 build/test command on the packaging VM. It builds node/UI images and runs disposable regtest, without creating an installer or touching installed services.
