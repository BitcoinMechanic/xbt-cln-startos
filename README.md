# XBT Core Lightning for StartOS

This package runs Core Lightning on Bitcoin BLAKE2b with the CLN Application UI and optional bounded swap-controller integration. Its service ID is xbt-cln; it is not the BTC c-lightning package.

## Integration status

This branch reconciles the tested XBT package with the generic package baseline. Development requires Node.js 22 or newer; the package requires StartOS 0.4.2 or newer. The native engine and sealed swap runtime remain the tested implementations.

**Do not publish or deploy this integration candidate yet.** A clean build still requires reconstruction of the accepted native images: Dockerfile.live requires local CLI_IMAGE, PARENT_IMAGE and gRPC donor images, plus a staged runtime. The older Dockerfile does not reproduce the later native engine. Locally packing accepted image archives is not proof of a reproducible clean build. StartOS lifecycle acceptance of the reconciled package also remains required.

## Chain and service boundaries

The native fork retains wire network bitcoin, invoice HRP bc, and storage directory bitcoin. Mandatory XBT feature bits and the pinned activation checkpoint authenticate the chain. Do not rename those native fields.

Backend selection prefers the installed knots-blake2b service and otherwise uses bitcoind. An unavailable preferred backend never silently switches the wallet to another service. Both must pass XBT checkpoint checks. Pruning requires the BLAKE2b companion's fetching proxy and historical block availability.

Arbitrary BTC or experimental XBT state is refused. Updates from the accepted privkeyio line preserve identity and journals. No migration from the generic BTC package is advertised. CLBOSS, Sling, watchtower activation and the generic package's VPN/payment actions remain unregistered until XBT compatibility is established.

The main volume contains wallet/channel data, settings, UI state and coordinator records. The public volume contains scoped local-controller credentials; it is not publicly shareable discovery metadata. Only the intended local controller should mount it read-only.

The lightning-sub runs the native node and mandatory hook plugins. The cln-application-sub runs the UI. Internal ports include peers (9735), CLNrest (3010), native gRPC (2106) and UI (4500). Clients must use actual StartOS interface addresses. CLNrest uses HTTP internally and StartOS TLS externally; native gRPC uses mutual TLS over raw TCP passthrough.

Startup validates backend and wallet identity before launching. Rescan/restore flags are consumed only once RPC answers; clearing them must not restart the service. Unknown persisted settings survive SDK file-model writes. Configuration preserves literal repeated values and bare flags.

## UI and controller integration

The UI includes channel labels, counterparty endpoints, splice controls and pending confirmation status. Long labels and liquidity bars remain within channel panels. Fiat conversion is local, using shared Neoxa XBT/USDC quotes and FX rates; wallet amounts are not sent to price services.

Ordinary UI payment requires the mandatory XBT invoice feature. A generic BTC invoice is rejected despite its similar HRP. BOLT12 controls remain disabled pending XBT validation.

StartOS actions provide configuration, node info, seed display, runes/revocation, password reset, rescan and coordinator setup. Enable Trust Local Swap Controller to maintain scoped grants when suitable connected liquidity exists. The helper publishes public/swap-controller.json for a local controller's read-only mount.

Renewal respects active swaps, manual grants, pauses and restore fences. Idle grants can refresh after a proven confirmed splice or eligible channel changes; historical funding references remain unchanged. Bounded journal history still requires safe maintenance when full. Disabling trust pauses new managed use while retaining recovery; deadline protection may force-close a receiving channel.

## Backups

Backups preserve keys and static channel recovery data, not a resumable channel database. Exclusions include the channel database/WAL, RPC socket, gossip, private runes, coordinator execution state and local-controller authorization. The public volume is excluded.

Restore clears publication/trust, writes a recovery marker and requests rescan/recovery. Existing swaps must resolve before these operations can proceed. Recovery depends on peers closing channels and may require draining recovered funds before starting fresh. Never restore as a way to retry an uncertain payment or reset grants.

## Build and validation

assets/source-lock.json records historical native/UI source inputs; it does not reproduce every later accepted native overlay. assets/swap-node is the exact sealed Python snapshot. assets/swap-runtime-source.json records provenance and native reconciliation requirements. Dockerfile.ui builds a pinned upstream UI with a checksummed patch. See UPDATING.md for update gates.

Development commands:

    npm ci
    npm run check
    npm run test:package
    node scripts/test-local-trust.cjs
    npm run build
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=assets/swap-node python3 -B -c "import package_verify; package_verify.verify('assets/swap-node', 'node')"
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=assets/swap-node python3 -B -m unittest discover -s assets -p test_incoming_admission.py
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=assets/swap-node python3 -B -m unittest discover -s assets -p test_timelock_errors.py

The broader local-controller tests also use test_coordinator_admin and its fixtures from the matching engine checkout. Preserve that provenance. Funded crash/replay/recovery tests are separate from mocked package tests. Type checks, bundling and local packing do not establish StartOS runtime acceptance.

Preserve the clboss and rust-teos gitlinks; do not accidentally change their pins when staging other work.
