#!/bin/bash
set -euo pipefail
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: bash scripts/test-image-recovery.sh IMAGE PATH_TO_KNOTS_BITCOIND [--empty-scan|--wallet-actions|--channel-actions]" >&2
    exit 2
fi
repo=$(cd -- "$(dirname -- "$0")/.." && pwd)
bitcoind=$(realpath -- "$2")
test -f "$bitcoind" && test -x "$bitcoind"
results=$(mktemp -d /tmp/xbt-image-recovery.XXXXXX)
echo "Disposable logs: $results"
docker run --rm --network none --init \
    -e XBT_DISPOSABLE_CONTAINER=1 \
    --mount "type=bind,src=$bitcoind,dst=/test-bitcoind,readonly" \
    --mount "type=bind,src=$repo/tests/image_recovery.py,dst=/image_recovery.py,readonly" \
    --mount "type=bind,src=$repo/assets/xbt,dst=/recovery,readonly" \
    --mount "type=bind,src=$results,dst=/results" \
    --entrypoint /opt/xbt-venv/bin/python "$1" /image_recovery.py "${@:3}"
