#!/bin/bash
# Extract the immutable Python bundle from a stopped image; never starts a node.
set -euo pipefail
image=${1:?Usage: bash scripts/test-gate-source.sh IMAGE}
work=$(mktemp -d /tmp/xbt-gate-source.XXXXXX)
container=''
cleanup() {
  if [ -n "$container" ]; then docker rm -v "$container" >/dev/null; fi
  rm -rf "$work"
}
trap cleanup EXIT
container=$(docker create "$image")
docker cp "$container:/usr/local/libexec/xbt-swap/." "$work/"
XBT_GATE_TEST_SOURCE="$work" python3 tests/test_gate.py -v
