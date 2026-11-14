# Empty-wallet StartOS acceptance

This procedure applies to candidate 0090b, package `xbt-cln`, version
`#privkeyio:26.6.9:1`, on a separate x86_64 test StartOS instance. Its installer
SHA256 is `f090d53d1d1482fbd153db47d9dd2bf89e53c97ae21dcb561356144538b632d0`.
Use a fresh, never-funded wallet and the same-host synced, unpruned BLAKE2b
Knots dependency. Do not import an existing experimental wallet or channels.

## Fresh startup

Install the candidate, set a test dashboard password and wait for node/UI
readiness. Check XBT labels, zero balances, no channels, address generation
without funding, and logout/login. Restart the service and check the password
and identity again. Record a host reboot separately if performed; do not
infer it from a service restart.

Keep receipts on the tower, outside the service volume. In the commands below,
run from the XBT package source checkout. Set `test_ssh` to the separate test
StartOS SSH destination.
The scripts select `lightning-sub`, pass Python as an argument vector, and send
the script with `-c`. A combined executable string such as `'python3 -'` is
incorrect. Do not pipe the script through package attach's stdin.

```bash
read -r -p "Test StartOS SSH destination (user@host): " test_ssh
receipt_dir="$HOME/code/cln-blake/installers/f2ee068848bd"
```

## Canary before backup

The following step deliberately writes one non-secret datastore marker. The
probe refuses funded wallets, current/closed channels, payment history,
restored wallets, mismatched identity and active swap journals. The canary
must be created before the backup and must never be recreated after restore.

```bash
python3 scripts/startos_acceptance.py --receipt-dir "$receipt_dir" \
  --destination "$test_ssh" --probe before-backup
```

Require PASS, an empty synced wallet, no restored marker and a present canary.
The resulting JSON captures the identity for this exact backup cycle.

## Backup, then inspect the original node

Use StartOS to create a new backup of XBT Core Lightning only. Wait for backup
completion and restart the service if necessary. Check the dashboard password.

```bash
python3 scripts/startos_acceptance.py --receipt-dir "$receipt_dir" \
  --destination "$test_ssh" --probe after-backup
```

Require the same identity, no restored marker and the canary still present.
Keep the before/after receipts. Then restore this exact backup through StartOS,
replacing only this empty test package as its UI requires. Leave Knots intact.
Do not run the original and restored node concurrently.

## Start the restored node

A restored package may initially be stopped: start XBT Core Lightning.
`package.attach: no matching subcontainers` means there is no running
`lightning-sub`; it does not demonstrate a recovery failure.

The warning to recover and drain funds is expected and persistent. This wallet
is empty. Leave it running while emergency recovery, preparation of 10,000
addresses and credential regeneration complete. RPC and native plugins may be
ready while `restore_pending` is still true. Do not clear the flag manually or
repeat the restore. Wait for the Web UI and verify the original password.

```bash
python3 scripts/startos_acceptance.py --receipt-dir "$receipt_dir" \
  --destination "$test_ssh" --probe restored
python3 scripts/startos_acceptance.py --receipt-dir "$receipt_dir"
```

Require all three receipts to pass: original fingerprint and engine hash,
empty wallet, canary absent after restore, restored marker present, at least
one preserved recovery copy, no pending recovery/rescan and node/plugins ready.
Restart once more to check the warning and identity persist if not already
observed in this acceptance session.

## Rescans are a separate check

The empty-wallet canary test does not need a full historical rescan. For an
explicit recent-block rescan, use the package's Rescan Blockchain action and
enter a known nearby starting block as a **negative** number. For example,
`-976900` starts from block 976900. Positive `976900` means rewind 976900 blocks
and may therefore start near genesis. Confirm the leading minus sign before
submitting; use `listconfigs rescan` to inspect the effective daemon setting.
Never select a shortened range for a funded recovery without accounting for
the wallet's complete history. A full scan uses `-1` and can take many hours.

## Recorded scope

The 2026-10-12 operator reports establish empty-wallet StartOS startup, UI
password persistence, service restart, a recent-block rescan, and the actual
backup/restore canary transition. Full-history rescan and funded recovery were
tested separately in regtest, not on this StartOS wallet. The exact StartOS
version and host-reboot-specific outcome were not separately reported.
Funded StartOS recovery, legacy channel migration, offline peers and migrated
swap activation remain outside this acceptance. Bundled swap modules remain
inactive. Do not use the recovered test identity for new channels or swaps.
