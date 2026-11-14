# XBT Core Lightning

This is an XBT (Bitcoin BLAKE2b) node, not a BTC/SHA256 node.

**This integration candidate is not ready for deployment.** The clean build depends on locally staged native images, and the reconciled package has not completed StartOS lifecycle acceptance. Keep an existing funded installation on its accepted package. This candidate requires StartOS 0.4.2 or newer.

## Prerequisites

Run a synchronized BLAKE2b Bitcoin backend. The package prefers an installed knots-blake2b service, otherwise bitcoind. The fallback must also be on the XBT chain. An unhealthy preferred backend does not trigger switching. Chain identity and the activation checkpoint are verified before use.

Pruned operation requires the companion's fetching proxy and historical block availability. Generic pruned fallback nodes are refused. Do not copy a BTC wallet or an unrelated experimental XBT channel database into this service.

## Open the UI

Use the Web UI address under Interfaces and set its initial password. Node Info shows identity and reachable peer endpoints. Use actual StartOS addresses for external wallets, not 0.0.0.0 or guessed internal ports.

Use HTTPS with the StartOS certificate trusted on the client, or onion interfaces over Tor. CLNrest uses a private rune; native gRPC uses client certificates.

Reset Password allows replacing a forgotten UI password without resetting wallet keys. Open the UI at its direct StartOS address afterward. Different services on one hostname can share cookies despite different ports; separate hostnames or browser profiles avoid that collision.

## Funds and channels

Back up before funding. Obtain an XBT on-chain address, then open a channel with an XBT peer once funding is usable. Channel details provide counterparty information, labels, funding references and splice controls. Splicing requires peer support and confirmations; finish a pending splice before another channel operation.

Ordinary payments require XBT invoices. BTC invoices require a separate swap controller. Channel capacity is not usable liquidity: reserves, HTLCs, fees and connectivity matter. CLBOSS, Sling, watchtowers and BOLT12 are not supported until compatibility is validated.

## Local Swap Controller

Install compatible Swap Controller and BTC Core Lightning packages on the same StartOS server. Both nodes need on-chain funds, connected channels and suitable liquidity.

Enable Trust Local Swap Controller on each node. Scoped grants and renewal are automatic; routine operation does not require individual grant approvals. The controller discovers private local publications and pairs the nodes.

Waiting may indicate insufficient liquidity, disconnected channels, active recovery or full history. Inspect detailed status rather than deleting records or reinitializing a funded service. Grant authority can include force-closing a receiving channel to protect a deadline. Disabling trust stops new managed use without erasing recovery records.

Public discovery and Wallet Swap API access are configured in the controller, not in this node's CLNrest settings. Node runes and wallet API keys are different credentials.

## Backups and recovery

Keep StartOS backups and key/recovery information offline. Backups intentionally do not restore a live channel database or coordinator spending authority. Restoration clears controller authorization and enters recovery/rescan mode. It may close channels and depends on peers.

Resolve swaps before backup/restore. Keep wallet volumes through validated updates. An update is not a restore or permission to import another chain's wallet.

## Troubleshooting

Check backend sync, historical block availability, peer connections, usable balances and the full error/reference. A timeout is not proof that no remote action occurred; inspect the saved swap before retrying.

Do not delete journals, change chain identifiers, remove recovery fences or replace native engines to bypass errors. Preserve diagnostic references, but never publish seeds, runes, private API keys or wallet files.
