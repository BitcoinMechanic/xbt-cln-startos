0097 — Checkpoint reviewed on-chain retirement and BTC recovery fees

Base tag: privkeyio-deadline-20261013
New tag:  privkeyio-retirement-20261014

Three source commits: lightning / privkeyio-swaps, xbt-cln-startos /
privkeyio-node, swap-controller-startos / privkeyio-compat. The BTC package
gets a tag at its existing commit. The BTC engine patch lives in lightning's
swap tools and is included in that source commit. Default branches stay unchanged.

1. PACKAGING VM — export the already-tested source

Download into ~/code/cln-blake/patches and transfer with your usual alias.
On the packaging VM:

  cd "$HOME/code/cln-blake/patches" &&
  unzip -n 0097-privkeyio-retirement-checkpoint.zip &&
  bash 0097-privkeyio-retirement-checkpoint/export-vm.sh \
    --results-dir /tmp/privkeyio-0096a-results.3pjwbd73

Source defaults to ~/code/cln-blake/privkeyio-migration. A positional path
selects a moved migration workspace; --results-dir selects moved results.

The exporter checks the actual final and raw receipts: 169 passing units with
no skips, six funded retirements with original recovered inputs/default fees,
six service regressions, signed and serialized BTC fee controls, unchanged XBT,
and the retained historical evidence. It binds all sources to the annotated
checkpoint ancestry and exact gitlinks. No test rerun, Docker invocation,
installer build, source edit or live-node access is performed.

Expected output:
  EXPORT READY: .../checkpoints/privkeyio-retirement-20261014/source-export.zip
  SHA256: ...

Only selected source patches and validated public receipts are exported.
Raw logs, private journals, runes, endpoints, certificates, binaries and unlisted
operator files remain on the VM. Historical evidence keeps its original
provenance; the failed 0096 run is never counted as passing funded evidence.

2. TOWER — reuse existing clones; commit, tag and push

Copy the exported source-export.zip to ~/tmp/swap-checkpoint-0097/ on the tower.
Compare its sha256sum with the value printed by the exporter, then:

  unzip -n "$HOME/tmp/swap-checkpoint-0097/source-export.zip" -d "$HOME/tmp/swap-checkpoint-0097/" &&
  bash "$HOME/tmp/swap-checkpoint-0097/0097-privkeyio-retirement-checkpoint/checkpoint-tower.sh"

Existing clones default to ~/code/cln-blake. Detached worktrees are created
at ~/tmp/cln-privkeyio-retirement-checkpoint. --cache-root PATH overrides the
clone location; a positional path overrides worktree storage. GitHub HTTPS/SSH
origins with or without .git are accepted. No new Lightning clone is downloaded.
Existing checkout files, HEADs and staging indexes stay intact. All remotes are
checked before commits/pushes; no force pushes. Partial pushes can resume
without duplicate commits.

3. PACKAGING VM — sync only after TOWER PUSH COMPLETE

  bash "$HOME/code/cln-blake/patches/0097-privkeyio-retirement-checkpoint/sync-vm.sh"

All four repositories are checked before any stash. Tested source and unrelated
untracked notes are stashed, then fast-forwarded to the checkpoint. Older
stashes remain. Do not pop them onto the already-applied checkpoint. Unexpected
or staged changes are retained and cause refusal.

This is a regtest source/evidence checkpoint, with no new installer or production
activation. On-chain history becomes terminal only after separate, explicit
coordinator and controller review of the original proofs and payment attempt.
Grant renewal keeps history and consumed budgets and requires fresh eligible
funding. Coordinator-aware funded backup/restore and a production migration
path remain separate milestones.
