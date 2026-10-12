# XBT Core Lightning — privkeyio migration candidate

0086 integrates the pinned swap-capable engine with the full node package and CLN Application 26.09. It is a **fresh-wallet candidate**. The supplied validation builds Docker images and runs isolated regtest; it does not produce or install an s9pk. Existing experimental XBT wallets, funded channels, grants and controller records must remain with their original implementation until a migration is explicitly validated.

## Identity and build

- StartOS package ID: `xbt-cln`, distinct from BTC `c-lightning`.
- Candidate version: `#privkeyio:26.6.9:0`; upgrades and downgrades are refused.
- Engine: `BitcoinMechanic/lightning` commit `ddd89e1d70d0ba415880a0ff02db7b053c73a298`, tree `21369587e10687c21634ec2b1d15a5de6db09496` (0085 checkpoint).
- Engine version: `v26.06.9-blake2b.7-swap0088b`; full C/Rust build includes native CLNrest, gRPC, askrene, xpay, bookkeeper, sql and chanbackup.
- UI: ElementsProject CLN Application 26.09, commit `ff2d698b4f64c86d950d6abe61bd6b8a0b52a68c`, adapted by the checksummed source patch `assets/ui-xbt.patch`.
- Docker recipes and `assets/source-lock.json` pin sources. The tower checkpoint workflow remains unchanged.

The privkeyio fork deliberately retains wire network `bitcoin`, invoice currency `bc`, and the `bitcoin/` data directory (regtest uses `regtest`/`bcrt`). These names do **not** establish BTC or XBT identity. XBT node/invoice feature bit 512 is required; node capability bit 515 announces unified signing and newly funded channels persist channel type bit 514. Do not normalize these fields to the legacy experimental `xbt` profile.

Before launching lightningd, StartOS checks the dependency's main chain, unpruned state, completed initial sync, BLAKE2b activation at 961640 and exact activation hash. An ordinary `bitcoind` package ID/version is insufficient. Node readiness also checks the fork's actual feature vectors before the UI starts. The mainnet startup path has no regtest bypass.

## Runtime and interfaces

The main volume is mounted at `/root/.lightning`. StartOS reaches Knots through its RPC bridge and mounts its cookie read-only at `/mnt/bitcoin`. Wallet layout is bound by `xbt-package-identity.json`; foreign/legacy layouts are rejected without moving or deleting them.

The `lightning-sub` runs the engine. The `cln-application-sub` runs the UI backend and serves its built frontend. Native REST carries named JSON object parameters. CLNrest speaks HTTP inside StartOS; the external LAN/clearnet edge supplies TLS. UI cookies retain the upstream HTTPS deployment setting. gRPC uses native mutual TLS passthrough. No nonexistent HTTP JSON-RPC service is exported on port 8080.

Available node operations include wallet addresses, deposits/withdrawals, channel management, BOLT11 invoices/payments, ordinary keysend, forwarding settings, peer/node information, SQL-backed history, seed display, rescans, UI password reset and rune management. Local tests do not establish every feature's live behavior.

The UI identifies the node and coin units as XBT, uses the XBT explorer, and displays fiat as unavailable instead of valuing XBT at BTC's fiat price. Before a UI BOLT11 payment is submitted, authenticated decode must show the mandatory XBT bit. A plain BTC invoice is rejected even though generic decode accepts the shared HRP. BOLT12 offer controls are disabled in this candidate pending their chain-boundary validation. UI ordinary payments are separate from the swap worker's single-part, single-attempt policy.

CLBOSS remains excluded because its external swaps assume BTC. TEOS/watchtower and Sling are not included or offered by this candidate; their fork compatibility is unverified. Currencyrate and BTC-oriented LSPS/BIP353 plugins are disabled. Core plugins and both submodule pins remain tracked; no submodule gitlink is changed.

## Swap service boundary

The exact checkpoint's `tools/swap` modules are included outside automatic plugin discovery at `/usr/local/libexec/xbt-swap`. They remain regtest-only and **inactive**. No grants, customer facade, controller actions or automatic mainnet swap worker are registered here. Existing installed direct/routed swaps remain on the legacy packages. This node-only package refuses detected migration authority journals rather than silently omitting them from a backup.

## Backups and restore

StartOS stops the service before backup. The backup excludes `bitcoin/lightningd.sqlite3` and WAL/SHM sidecars, the RPC socket, gossip, logs and the UI's generated rune file. It retains wallet keys, emergency channel recovery data, identity marker, settings and UI password configuration.

Restore validates the package layout, writes a persistent recovery marker, preserves a separate copy of `emergency.recover`, drops the old UI rune file and requests emergency recovery plus wallet address pre-generation. A fresh UI rune is minted from the restored node. UI startup waits for the restore oneshots. Rescan/restore flags are consumed only after RPC and the required recovery work succeeds; a failed startup does not consume them. A persistent health warning identifies the restored wallet on later restarts. Recover and drain funds; do not open new channels or activate swaps on restored state.

0088 adds a funded recovery fixture. 0088b retains the exact 0086 UI and applies the checksummed `assets/engine-recovery-fees.patch` to the pinned engine. It corrects the missing witness-script weight for recovered anchor-channel outputs, including the longer supported lease scripts. The build runs the same seven serialized-witness cases against the original and patched estimator. Default-fee withdrawals remain mandatory; no fixture fee override or relay-policy relaxation is used. Backup exclusions, filesystem hooks and recovery commands are shared in `startos/recovery.ts`; the refactor preserves their behavior. The fixture excludes the channel database, advances both channels with payments after the backup, stops the original wallet permanently, restores its older keys and SCB into a fresh database, recovers both opener/recipient channel roles, interrupts recovery, and performs a full rescan after address pre-generation. Both peers must close the original channels, all three nodes must drain to fresh destinations with unified signatures, and a confirmed transaction ledger must reconcile deposits, withdrawals, mining fees and any unspent 330-sat anchors.

The wallet's active derivation counter is BIP32 **or** BIP86, depending on its secret format. Address pre-generation remains bounded at 10,000 calls; it is not an unlimited gap search. The fixture uses both address types beyond a 128-address unused gap and first demonstrates that an ordinary full rescan misses them. The operator-requested full rescan remains necessary after pre-generation.

The fixture adapts only stopped directory names (`regtest/` ↔ `bitcoin/`) and CLI network arguments. It does not run the StartOS supervisor or rsync transport. Actual StartOS backup/restore, higher address indexes, offline/uncooperative peers and migration of existing installed XBT channels remain release gates. A passing disposable fixture is not authority to reuse a recovered wallet or deploy this candidate.

## Validation

- `npm run check`, `npm run build`, `npm run test:package` validate types, bundled StartOS actions, backend/profile boundaries, foreign-state refusal, daemon ordering and backup/restore hooks.
- The patched UI builds from its original lockfile; `scripts/test-ui.mjs` verifies compiled UI admission boundaries.
- `scripts/test_node_ui.py` runs only with `--disposable-regtest`, creates its own nodes/backends, and uses the actual built UI server with password authentication and CSRF tokens. It checks BTC invoice rejection before payment, UI address/channel operations, four XBT payments and retained unified funding/signing after both nodes and UIs restart.
- `scripts/test_backup_recovery.py` is the separate 0088 funded backup/recovery gate. The runner retains the 0087 export by its exact SHA256 and refuses substitute images or a changed backend. 0088b incrementally rebuilds the patched engine from the cached 0086 build; the UI and recovery hooks are reused. It does not claim prior cases were rerun.
- Earlier swap-service evidence belongs to checkpoint 0085. This integration changes package runtime composition and therefore needs fresh packaged testing.

No installed service, private credential, existing wallet, production chain, Git ref, index or stash is used as a test target.
