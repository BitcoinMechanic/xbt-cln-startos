# Updating source inputs

This package uses a tested XBT engine and sealed swap runtime. A generic ElementsProject BTC release is not an equivalent rebuild.

## Native engine

assets/source-lock.json records the historical base and recovery-weight patch. The accepted later engine has additional startup/replay safeguards and a repaired gRPC binary. Dockerfile.live requires exact staged CLI_IMAGE, PARENT_IMAGE, gRPC donor image and runtime inputs. These remain local build inputs, not a self-contained release recipe.

Before releasing from a clean checkout, reconstruct verifiable inputs for that exact engine, prove native recovery behavior, and supply both advertised architectures. Do not substitute a similarly named engine merely to make packaging succeed.

assets/swap-runtime-source.json records the upstream engine comparison. Important-hook teardown, final-HTLC replay in closing states and anchor witness weight must be checked against the actual replacement. Run original/patched crash, replay and on-chain recovery fixtures before replacing native binaries.

## Python runtime

assets/swap-node is the complete tested, already-patched snapshot. Verify it:

    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=assets/swap-node python3 -B -c "import package_verify; package_verify.verify('assets/swap-node', 'node')"

Copy the entire directory without adding __pycache__ or modifying its contents. Do not reapply the historical patches/timelock-patches.json chain. Move the production Docker recipe to this verified input only as part of a complete validated clean-build change.

## CLN Application

Dockerfile.ui pins the source commit, build-image digests and patch checksum. Upstream is https://github.com/ElementsProject/cln-application. Check assets/ui-xbt.patch against the chosen commit with git apply --check, update its checksum, and run the backend/frontend tests and production build specified in that Dockerfile. Preserve XBT invoice validation, local fiat conversion and bounded channel layouts.

## External contracts and packaging

startos/backend.ts and startos/init/watchHosts.ts record checked source commits for Bitcoin RPC and Tor SOCKS constants. They intentionally avoid importing another service's full SDK runtime. Verify these contracts when changing supported backends.

The CLBOSS and TEOS submodules are retained but not activated; preserve their pins. For SDK updates, follow the workspace guide, review crossed breaking changes, stabilize the npm lockfile, and rerun package/runtime validation.
