0093 — Checkpoint the passing 0092a coordinator administration milestone

Base tag: privkeyio-startos-empty-20261012
New tag:  privkeyio-coordinator-admin-20261013

Three source commits: lightning / privkeyio-swaps, xbt-cln-startos /
privkeyio-node, swap-controller-startos / privkeyio-compat. The BTC package
gets a tag at its existing commit. Default branches are unchanged.

1. PACKAGING VM — export the already-tested source

Download into ~/code/cln-blake/patches and transfer with your usual alias.
On the packaging VM:

  cd "$HOME/code/cln-blake/patches" &&
  unzip -n 0093-privkeyio-admin-checkpoint.zip &&
  bash 0093-privkeyio-admin-checkpoint/export-vm.sh \
    --results-dir /tmp/privkeyio-0092a-results.n6T0lywn

Source defaults to ~/code/cln-blake/privkeyio-migration. A positional path
selects a moved migration workspace; --results-dir selects moved results.
The exporter requires the passing 0092a source and raw receipts. It validates
all 120 unit tests, eight grant setups, six service scenarios, populated
restore checks, compiled-engine provenance, historical evidence and tags.
No test rerun, Docker, installer build, source edit or live-node access.

Expected output:
  EXPORT READY: .../checkpoints/privkeyio-coordinator-admin-20261013/source-export.zip
  SHA256: ...

Only selected source patches and validated public receipts are exported.
Raw logs, private journals, credentials, endpoints, certificates, binaries and
unlisted operator files stay on the VM. Earlier evidence stays historical;
the new result does not claim those earlier cases ran under 0092a.

2. TOWER — reuse existing clones; commit, tag and push

  mkdir -p "$HOME/tmp/swap-checkpoint-0093" &&
  scp start9packaging@192.168.8.176:/home/start9packaging/code/cln-blake/privkeyio-migration/checkpoints/privkeyio-coordinator-admin-20261013/source-export.zip \
    "$HOME/tmp/swap-checkpoint-0093/"

Compare with the SHA256 printed on the VM:

  sha256sum "$HOME/tmp/swap-checkpoint-0093/source-export.zip"

Then:

  unzip -n "$HOME/tmp/swap-checkpoint-0093/source-export.zip" -d "$HOME/tmp/swap-checkpoint-0093/" &&
  bash "$HOME/tmp/swap-checkpoint-0093/0093-privkeyio-admin-checkpoint/checkpoint-tower.sh"

The tower uses existing clones at ~/tmp/cln-pre-privkeyio-checkpoint and makes
detached worktrees at ~/tmp/cln-privkeyio-admin-checkpoint. --cache-root PATH
selects a moved clone cache; a positional path selects new worktree storage.
Existing tower checkout files, HEADs and staging indexes stay untouched.
The tower verifies all four remotes before committing/pushing, never force
pushes, and can resume partial pushes without creating duplicate commits.

3. PACKAGING VM — sync only after TOWER PUSH COMPLETE

  bash "$HOME/code/cln-blake/patches/0093-privkeyio-admin-checkpoint/sync-vm.sh"

All four repositories are checked before any stash. Exact tested source is
stashed with unrelated untracked notes, then fast-forwarded to the checkpoint.
Older stashes remain. Do not pop them onto the already-applied checkpoint.
Unexpected or staged source changes are retained and cause refusal.

This checkpoint is regtest source/evidence only. The stopped-state restore
tests prove refusal to execute restored authority; they do not establish
funded coordinator wallet recovery or enable production coordinator swaps.
