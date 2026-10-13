# XBT Core Lightning

This migration candidate adds a wallet and channel dashboard to the XBT node. It requires synced, unpruned BLAKE2b Knots. It is not yet an update for your installed experimental XBT node.

The dashboard supports XBT wallet addresses, channels, BOLT11 invoices and payments. Set its own password on first use. XBT units and explorer links are explicit; fiat estimates are unavailable. BTC invoices are refused before payment. BOLT12 offers, external watchtowers and automatic rebalancing are not enabled in this candidate.

The node verifies the BLAKE2b backend before creating or opening its wallet. Internally the fork still calls its network and wallet directory `bitcoin`; that name does not mean it is following BTC.

Backups preserve keys and emergency channel recovery data, not a copy of the live channel database. A restored node attempts recovery, asks for a rescan and remains marked as restored. Recover and drain funds before starting fresh. Funded regtest recovery and empty-wallet StartOS backup/restore have passed; funded StartOS recovery remains to be validated. Recovery depends on peers cooperating, and the automatic address window is bounded.

Your existing swap controller and nodes remain in use. The migrated swap modules are bundled but not activated by this package. Do not import an existing experimental XBT wallet or channel directory into it.

The retained 0088b fixture verified funded regtest recovery and default-fee withdrawals. The 0090b x86_64 test installer reuses that engine and the validated UI. Historical fixture runners retain their original checkpoint requirements; a source checkpoint does not require rerunning or rebuilding them.

The 0090b startup correction accepts Knots' top-level BLAKE2b activation metadata. It preserves all chain and synchronization checks. Version `#privkeyio:26.6.9:1` can update the prior `#privkeyio:26.6.9:0` candidate in place; no wallet conversion is needed. Existing experimental XBT wallets and channels remain unsupported.


## Empty-wallet StartOS acceptance

Candidate 0090b has passed the operator's empty-wallet StartOS startup and
backup/restore checks. The dashboard retained its password and node identity;
a database marker survived backup and disappeared after restoration.
This does not establish funded StartOS recovery or legacy channel migration.

After restoring, start the service and allow emergency recovery and preparation
of 10,000 addresses to finish. A ready RPC interface does not mean these steps
are complete. The recovered-wallet warning remains by design. An empty test
wallet has no funds to drain, but its restored identity must not be reused for
new channels or swaps. A canary check does not need a full historical rescan.

For Rescan Blockchain, a negative number selects an absolute starting block:
`-976900` means start at block 976900. A positive number is a rewind depth and
can unintentionally select almost the entire chain. Funded recovery must cover
the wallet's relevant history; `-1` scans from block 1 and can take many hours.
