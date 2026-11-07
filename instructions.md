# 0102 dedicated live integration candidate

Build this candidate with the verified 0102 bundle runner. It binds exact engine,
UI and Python-runtime image IDs into an isolated packaging copy and compiles the
installed StartOS registry. The source manifest alone is not an installer.

Start the native node, wait for chain synchronization, and open/fund channels
normally. Open Enable Swap Coordinator and confirm once. Restart the service;
then review and confirm separate incoming/outgoing bounded grants. Copy each
bounded controller credential into the controller pairing action. No SCID entry
is required. The actual incoming channel is bound when the payment arrives.

The CLNrest interface must be enabled. Use its StartOS HTTPS URL (without a wallet
scheme prefix or embedded rune) and the corresponding root CA when pairing.
The native web UI and ordinary payments remain available.

This revision can update the accepted privkeyio XBT candidate :1 to :2 on the
same volume. Existing identity, unified-signature channels, UI password and
journals remain in place. It refuses the old experimental XBT wallet layout.

Ordinary restart/update is not backup restoration. Restored wallets remain fenced
from new coordinator authority; recovery may force-close channels. Incoming
swap deadline protection can also close the actual receiving channel if a swap
cannot resolve before its approved deadline. Grants require explicit review.

0102 validation distinguishes synthetic mainnet policy checks, actual funded
regtest fixtures, packed-file checks, and pending StartOS host acceptance. It
does not claim a mainnet swap or StartOS host test from a regtest receipt.

### Updating from `26.6.9:2`

Version `26.6.9:3` restores a missing bundled gRPC plugin that caused startup
to fail with `grpc-port: unknown option`. Use the normal package update on the
existing volume. After startup, verify the node identity and existing channels.

Retire unused outgoing swap authority without waiting for the recipient invoice to expire. Requires no send intent and fresh unused-payment/channel checks; permanently prevents later sending and preserves budgets, records, wallets and channels.

For the expiry-workflow release, update the BTC and XBT coordinator packages before the controller. Existing unpaid expired swaps are then retired automatically after fresh unused-authority checks; no journal deletion or initialization is needed. Retired enrollments still consume their original grant slot and budget. A later swap may require a newly reviewed grant. Ten-minute pricing applies only to new controller quotes; never pay a previously expired invoice.


## Automatic local Swap Controller connection

With Swap Controller installed on this StartOS server, enable the coordinator and
review/confirm incoming and outgoing grants as usual. Run **Connect Local Swap
Controller** once and enable local connection. The controller discovers this node,
its HTTPS endpoint and the server certificate automatically; credentials do not
need to be copied. Confirming a replacement grant updates the shared connection.

Only current, unpaused, unexpired, explicitly approved bounded grants are shared.
The `public` volume contains `swap-controller.json` for local dependent services;
it never contains a general administration rune. That volume and the opt-in marker
are excluded from backups. Restore clears sharing and retains the authority fence.
Disabling sharing stops automatic configuration; it does not revoke credentials
already saved for approved swaps. Use Pause Grant when stopping new grant use.

This does not open channels, fund liquidity, approve grants or raise spending limits.
The controller preserves manual pairings and waits for active swaps to finish before
selecting changed local grants. Older packages without this connection contract
continue to require manual pairing.
