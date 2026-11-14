0095 — Checkpoint the passing 0094a deadline protection milestone

Base tag: privkeyio-coordinator-admin-20261013
New tag:  privkeyio-deadline-20261013

Three source commits: lightning / privkeyio-swaps, xbt-cln-startos /
privkeyio-node, swap-controller-startos / privkeyio-compat. The BTC package
gets a tag at its existing commit. Default branches are unchanged.

1. PACKAGING VM — export the already-tested source

Download into ~/code/cln-blake/patches and transfer with your usual alias.
On the packaging VM:

  cd "$HOME/code/cln-blake/patches" &&
  unzip -n 0095-privkeyio-deadline-checkpoint.zip &&
  bash 0095-privkeyio-deadline-checkpoint/export-vm.sh \
    --results-dir /tmp/privkeyio-0094a-results.dG9bfyO7

Source defaults to ~/code/cln-blake/privkeyio-migration. A positional path
selects a moved migration workspace; --results-dir selects moved results.
The exporter checks all 149 passing units, six funded deadline cases, six
service regressions and the retained original engine/replay/fee controls.
It validates raw receipts as well as the final summary, exact source trees,
annotated checkpoint ancestry and gitlinks. No test rerun, Docker invocation,
installer build, source edit or live-node access.

Expected output:
  EXPORT READY: .../checkpoints/privkeyio-deadline-20261013/source-export.zip
  SHA256: ...

Only selected source patches and validated public receipts are exported.
Raw logs, private journals, runes, endpoints, certificates, binaries and
unlisted operator files remain on the VM. Retained results keep their original
provenance and are not relabeled as fresh tests.

2. TOWER — reuse existing clones; commit, tag and push

  mkdir -p "$HOME/tmp/swap-checkpoint-0095" &&
  scp start9packaging@192.168.8.176:/home/start9packaging/code/cln-blake/privkeyio-migration/checkpoints/privkeyio-deadline-20261013/source-export.zip \
    "$HOME/tmp/swap-checkpoint-0095/"

Compare with the SHA256 printed on the VM:

  sha256sum "$HOME/tmp/swap-checkpoint-0095/source-export.zip"

Then:

  unzip -n "$HOME/tmp/swap-checkpoint-0095/source-export.zip" -d "$HOME/tmp/swap-checkpoint-0095/" &&
  bash "$HOME/tmp/swap-checkpoint-0095/0095-privkeyio-deadline-checkpoint/checkpoint-tower.sh"

Existing clones default to ~/code/cln-blake. Detached worktrees are created
at ~/tmp/cln-privkeyio-deadline-checkpoint. --cache-root PATH overrides the
clone location; a positional path overrides worktree storage. Valid GitHub
HTTPS/SSH origins with or without .git are accepted. No new Lightning clone
is downloaded. Existing checkout files, HEADs and staging indexes stay intact.
All remotes are checked before commits/pushes; there are no force pushes.
Partial pushes can resume without duplicate commits.

3. PACKAGING VM — sync only after TOWER PUSH COMPLETE

  bash "$HOME/code/cln-blake/patches/0095-privkeyio-deadline-checkpoint/sync-vm.sh"

All four repositories are checked before any stash. Tested source and unrelated
untracked notes are stashed, then fast-forwarded to the checkpoint. Older
stashes remain. Do not pop them onto the already-applied checkpoint. Unexpected
or staged changes are retained and cause refusal.

This is a regtest source/evidence checkpoint. On-chain recovery remains
nonterminal and blocks grant reuse pending explicit retirement handling.
Coordinator-aware funded backup/restore and production activation remain
separate milestones. There is no new installer in this checkpoint.
