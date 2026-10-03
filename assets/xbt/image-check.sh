#!/bin/sh
set -eu
cd /usr/local/share/xbt-cln
[ "$(lightningd --version)" = "xbt-81ba4099a63e" ]
[ "$(lightning-cli --version)" = "xbt-81ba4099a63e" ]
bitcoin-cli --version > /dev/null
for name in run-block_blake2b run-bitcoin_block_from_hex run-xbt-chainparams run-xbt-maturity; do
    "/usr/local/libexec/xbt-selftest/$name"
done
printf '%s\n' 'XBT image checks OK (offline; no wallet or backend used)'
