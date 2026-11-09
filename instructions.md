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

For the expiry-workflow release, update the BTC and XBT coordinator packages before the controller. Existing unpaid expired swaps are then retired automatically after fresh unused-authority checks; no journal deletion or initialization is needed. Retired enrollments still consume their original grant slot and budget. With local controller trust enabled, replacement grants are automatic within the retained-history ceiling; manual setups still require a new grant. Ten-minute pricing applies only to new controller quotes; never pay a previously expired invoice.


## Automatic local Swap Controller trust

With Swap Controller installed on this StartOS server, run **Trust Local Swap
Controller** once on each Lightning node. Enable **Trust this local swap controller**.
This initializes the coordinator if needed and restarts the node. No individual
grant confirmations, endpoint entry or credential copying are needed afterward.
Legacy sharing-only opt-ins remain sharing-only until you explicitly enable trust.

The node creates incoming and outgoing scoped grants when suitable connected
channels have liquidity. Each grant lasts up to 24 hours and renews automatically
near expiry or when its remaining budget is too small for another maximum swap.
The XBT ceiling is 1,000,000 sats per swap, four swaps and 3,000,000 sats per grant
(or less when liquidity is lower), with a 10-sat outgoing fee limit. These are
per-grant limits, not lifetime spending limits: continuing trust authorizes renewal.
Version 26.6.9:9 replaces automatically managed old 10,000-sat XBT grants when
liquidity permits and no swap requires recovery. Manual and paused grants remain
unchanged. The BTC companion retains its separate 10,000-sat per-swap ceiling.
Incoming protection may close the receiving channel 72 blocks before its deadline.
Nodes without suitable channels wait; this setting never funds or opens channels.

Disabling trust pauses every automatically managed grant for new swaps, while
preserving outstanding recovery authority. Manually pausing a managed current
grant also stops automatic renewal until you explicitly enable trust again.
Unrelated manual grants are not revoked by this switch. Renewal waits while any
swap requires recovery. Existing manual pairings in the controller are preserved.

Only scoped credentials are published to the local dependent service through
`public/swap-controller.json`; no general administration rune is shared. Trust,
coordinator journals and published credentials are excluded from backups. Restore
clears the opt-in and retains the existing authority fence.

The existing finite coordinator journal still caps retained grants and enrollments
at 64 each. Automatic renewal stops with a history-full status at that ceiling;
it never deletes recovery history or silently resets budgets. Journal archival
is not implemented in this release. The Local Controller Trust health message
reports waiting, ready, paused, unavailable or history-full conditions.

The image contains `assets/local_controller_trust.py` outside the sealed swap
runtime. It verifies that runtime before opening its journals and holds the same
exclusive authority lock as the coordinator. A durable pending-grant record makes
retries recover the exact grant after an interrupted write. The helper exposes
only enable, maintain and disable operations to local package administration.


## Local BLAKE2b backend selection

XBT Lightning prefers the installed `knots-blake2b` service. Only when it is absent
does it select `bitcoind`. RPC discovery, read-only cookie mounts and dependency
health checks all use the same selected service. A stopped or unhealthy preferred
backend never triggers fallback. Installing/removing it updates the selection.
Both backends must still pass the BLAKE2b activation/checkpoint checks; an ordinary
BTC `bitcoind` is not an acceptable XBT backend. BTC Lightning is unaffected.

Pruning is supported with **knots-blake2b 29.4.3:1 or newer**, using its normal
RPC endpoint and bundled BLAKE2b-capable fetching proxy. Leave that service's
pruning/proxy configuration enabled; no extra credentials or proxy service are
needed. XBT Lightning checks the chain checkpoint and fetches a historical raw
block before starting. If old blocks are unavailable, startup waits and retries.
The `bitcoind` fallback still requires an unpruned backend.

CLN fetches missing history through the proxy during catch-up and rescans.
Recovery therefore depends on reachable archival BLAKE2b peers. If it stalls,
restore the backend/proxy's peer connectivity and retry; preserve the Lightning
wallet and channel state. Pruning support does not make old wallet imports or
backup restores safe; existing restore barriers remain in force.

Recipient invoice timelocks (including 80 blocks) are supported within the 576-block total route budget. The final hop must match the invoice, and the incoming swap deadline includes the outgoing route delay plus the existing recovery margin. Invoice timing, amount, timelock and route refusals have specific messages; unknown or uncertain failures remain private.
An unknown recipient with no routing hints is reported separately: create a fresh invoice in the connected receiving wallet with private-channel route hints enabled. Increasing fees does not supply missing routes.

New automatically managed outgoing grants allow up to 576 blocks of route delay. Existing idle managed grants refresh automatically; active recovery and manual grants are preserved. Incoming swap deadlines still cover the actual outgoing route delay plus 144 recovery blocks and 6 propagation blocks. Fee and hop limits are unchanged.
