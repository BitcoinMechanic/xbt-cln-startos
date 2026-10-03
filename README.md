# XBT Core Lightning for StartOS

Experimental fresh-wallet observation package for StartOS 0.4, forked from
Start9Labs/cln-startos at `6040fb4a8cfdaaa9ef8cd468e60c2e14a028c928`.

**Do not fund this package or migrate existing wallets yet.** The runtime and
package installation still require validation on StartOS. Only empty-wallet backup restoration is supported in this release; funded
wallet and channel recovery remain blocked.

## Identity and source

- Package: `xbt-cln`, wrapper version `0.1.0:1`.
- Wrapper: https://github.com/BitcoinMechanic/xbt-cln-startos
- Node: https://github.com/BitcoinMechanic/lightning
- Pinned node commit: `81ba4099a63e5a0e83f55cead53c54f2a1b3c1fe`.
- Binary version: `xbt-81ba4099a63e`.
- Image definition: `Dockerfile.xbt`; source/contract record: `assets/xbt/source-lock.json`.

Source is pinned; apt packages and base image tags are not a claim of bit-for-bit
reproducibility. The inherited `Dockerfile` and unregistered legacy action/config
sources remain as porting references. They are not the active XBT runtime.
The original CLBOSS and TEOS submodule pins remain unchanged.

## Runtime and backend contract

The sole `main` volume mounts at `/root/.lightning`; CLN's XBT wallet lives in its
`xbt/` subdirectory. CLI calls explicitly select `--network=xbt`.
`--conf=/dev/null` prevents inherited Bitcoin/plugin settings from being loaded.
Only the peer interface (TCP 9735) and read-only Node Info action are registered.
No web UI, remote wallet RPC interface, swap role, CLBOSS, Sling, watchtower,
custom VPN, or automatic public address announcement is enabled in this stage.
Start Tunnel and Tor operation will be validated separately.

The local backend dependency still has ID `bitcoind`, with host `rpc`, internal
port 8332, volume `main`, and cookie at its root. This matches Retropex/knots-startos
commit `813da42c9308e027f0c193e650142bcf37b2cd62` (`#knots:29.4.2:3`).
The bitcoin-core-startos TypeScript dependency supplies the structurally identical
mount type and RPC constants; it does not establish the backend's chain identity.

Before starting lightningd, an RPC preflight requires synced, unpruned mainnet,
active BLAKE2b at height 961640, and the pinned block hash
`0000000000000050c1e5f69672f459293be14f46e5a494e7a8c8541396f18eeb`.
The fork's bcli plugin independently enforces XBT identity during operation.
Backend credentials come from a read-only cookie mount, never from package inputs.
Cookie replacement triggers reconfiguration; temporary disappearance does not.

## Backups and observation limits

StartOS stops the service for the duration of each backup. The pre-backup hook
runs `assets/xbt/empty_backup.py` against the stopped SQLite database. It requires
the pinned XBT identity and no rows in channels, channel_htlcs, outputs,
transactions, payments or invoices. It refuses a nonempty WAL and missing schema.
It does not prove that a never-scanned external deposit cannot exist: the operator
must still keep this observation node unfunded.

A private `empty-wallet-backup.json` records the node ID and SHA256 bindings of
`xbt/hsm_secret` and `xbt/emergency.recover`. Both files remain in the backup.
The database, WAL/SHM, socket and gossip store remain excluded. This is an
integrity check for the observation workflow, not authentication against a party
who can alter the backup and its receipt.

Restore requires a fresh volume without a database. The post-restore hook writes
`restore-blocked` first, verifies the receipt and its files, then writes
`restored-identity.json` and clears the block. Every failed validation retains the
block. Startup verifies the restored node ID against the saved identity before
reporting green health. Older backups without a receipt remain blocked. Never
remove a blocking marker by hand or copy an old channel database into the volume.

Version 0.1.0:0 upgrades without moving wallet data. This does not implement
funded-wallet recovery, emergency channel closure, rescanning, or migration of the
tower's coordinators. No spending action is enabled.

## Local validation

```sh
npm ci --ignore-scripts
npm run check
npm run test:xbt
python3 -m venv .venv
.venv/bin/python tests/test_empty_backup.py -v
npm run build
npm run check:bundle
```

The policy checks are offline. The bundle check verifies the exported package ID,
version, image, dependency and action set. They do not emulate StartOS.

Build the source image on the amd64 tower (explicit TARGETARCH also works with the
legacy Docker builder):

```sh
docker build -f Dockerfile.xbt --build-arg TARGETARCH=amd64 \
  --build-arg BUILD_JOBS=28 --build-arg RUST_BUILD_JOBS=4 \
  -t xbt-cln:81ba4099a63e .
docker run --rm --network none xbt-cln:81ba4099a63e xbt-image-check
```

The source image and four native self-tests passed on the tower, and version
0.1.0:0 started and retained its identity across service restarts on StartOS.
This update adds one Python file to the runtime image, reusing the expensive
compile layers. Build the package in the VM with:

```sh
BUILDX_BUILDER=startos-builder make x86
```

The empty-wallet StartOS backup/restore round-trip passed with the same node ID.
The nine offline backup tests use synthetic SQLite fixtures; they do not claim
real channel recovery coverage.

## Packaged-image channel recovery fixture

The empty-wallet StartOS backup/restore round-trip passed with the same node ID.
`tests/image_recovery.py` now exercises a separate funded **regtest** wallet in
an isolated Docker container. It opens a channel, pays, cleanly stops the owner,
copies only `hsm_secret` and `emergency.recover` to a fresh directory, and asks
the surviving peer to close. Success requires spending a confirmed recovered
channel output into the peer's wallet. The original database is retained only
as a diagnostic artifact and is never copied into the recovered node.

Use the already-built package image and your BLAKE2b Knots executable:

```sh
docker image ls start9/xbt-cln/lightning
bash scripts/test-image-recovery.sh IMAGE_ID ../bitcoind
```

This does not rebuild the package. The launcher publishes no ports and uses
`--network none`; backend and Lightning traffic stays on container loopback.
Only the executable, test script and a newly created temporary results directory
are mounted. Logs and disposable regtest keys remain in that results directory.
The executable must run on Debian bookworm, the image's runtime base.

This fixture does not invoke StartOS backup hooks, permit funded backups, test
an offline surviving peer, or cover unresolved HTLCs. Keep the StartOS wallet
unfunded; production recovery policy is unchanged.
