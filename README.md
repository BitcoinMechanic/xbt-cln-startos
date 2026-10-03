# XBT Core Lightning for StartOS

Experimental fresh-wallet observation package for StartOS 0.4, forked from
Start9Labs/cln-startos at `6040fb4a8cfdaaa9ef8cd468e60c2e14a028c928`.

**Do not fund this package or migrate existing wallets yet.** The runtime and
package installation still require validation on StartOS. Backup restoration is
intentionally blocked until XBT channel recovery is implemented and tested.

## Identity and source

- Package: `xbt-cln`, initial wrapper version `0.1.0:0`.
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

Backups preserve the key and emergency recovery file but exclude the XBT live
SQLite database, WAL/SHM, RPC socket and gossip store. A post-restore marker blocks
startup. Do not remove that marker or import any existing wallet. Recovery support
is not part of this release. A detected `bitcoin/` directory also blocks startup.

## Local validation

```sh
npm ci --ignore-scripts
npm run check
npm run test:xbt
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

The image and four native self-tests already passed on the tower. The wrapper
uses the same image without recompiling it for these TypeScript changes. Actual
s9pk packing/install validation is the next step and requires StartOS `start-cli`.
