0099 — Checkpoint packaged swap runtimes and open-channel continuity

Base tag: privkeyio-retirement-20261014
New tag:  privkeyio-packaged-runtimes-20261014

Four source commits and four annotated tags on the existing migration branches:
lightning / privkeyio-swaps; xbt-cln-startos / privkeyio-node;
btc-cln-startos and swap-controller-startos / privkeyio-compat.
Default branches stay unchanged.

1. PACKAGING VM — export already-tested sources

Download into ~/code/cln-blake/patches and transfer with your usual alias.
On the packaging VM:

  cd "$HOME/code/cln-blake/patches" &&
  unzip -n 0099-privkeyio-packaged-checkpoint.zip &&
  bash 0099-privkeyio-packaged-checkpoint/export-vm.sh \
    --results-dir /tmp/privkeyio-0098a-results.r2pjegti

Source defaults to ~/code/cln-blake/privkeyio-migration. A positional path
selects a moved workspace; --results-dir selects moved results.

The exporter validates 177 units with no skips, all six funded packaged cases,
the exact source trees and annotated checkpoint ancestry, runtime import/file
manifests, six immutable runtime image IDs, the independent image inventories,
and equality of extracted runtime contents. Native engine and CLNrest hashes
must match retained 0096a evidence. The original parent inventory and every
required raw receipt must agree with the final result. Earlier receipts retain
their original provenance; they are not counted as new runs.

No Docker invocation, test rerun, source edit, build, installation, backup,
restore, channel closure or live-node access occurs during this checkpoint.
Private journals, logs, credentials, invoices, binaries and unlisted operator
files are not exported. The generated archive contains selected source patches,
validation tooling, public receipt metadata and exact content hashes.

Expected output:
  EXPORT READY: .../checkpoints/privkeyio-packaged-runtimes-20261014/source-export.zip
  SHA256: ...

2. TOWER — reuse existing clones; commit, tag and push

Copy that exported source-export.zip into ~/tmp/swap-checkpoint-0099/.
Compare sha256sum with the VM's printed value, then:

  unzip -n "$HOME/tmp/swap-checkpoint-0099/source-export.zip" -d "$HOME/tmp/swap-checkpoint-0099/" &&
  bash "$HOME/tmp/swap-checkpoint-0099/0099-privkeyio-packaged-checkpoint/checkpoint-tower.sh"

Existing clones default to ~/code/cln-blake. Detached worktrees are created at
~/tmp/cln-privkeyio-packaged-checkpoint. --cache-root PATH changes the clone
location; a positional path changes worktree storage. SSH/HTTPS origins with or
without .git are accepted. No new Lightning clone is downloaded. Existing
checkout files, HEADs and staging indexes stay intact. Every repository is
checked before any push; pushes are never forced. Partial pushes can resume
without duplicate commits.

3. PACKAGING VM — sync after TOWER PUSH COMPLETE

  bash "$HOME/code/cln-blake/patches/0099-privkeyio-packaged-checkpoint/sync-vm.sh"

All four repositories are checked before stashing. Tested source and unrelated
untracked notes are stashed, then fast-forwarded. Older stashes remain. Do not
pop them onto the already-applied checkpoint. Unexpected or staged work causes
refusal and is retained.

Scope of the accepted 0098a milestone

Both swap directions passed restart-held, off-chain failure and update-held.
The original persistent directories, identity, open funding channels, signing
types, TLS identity, bounded credentials, invoices, HTLCs and payment attempts
were retained, with twelve balances verified and no channel closures.

The image generations contain the same application code; their manifests have
different generation labels. The harness tests replacement with extracted image
contents. This is not an arbitrary engine/schema upgrade or a StartOS update
acceptance test. Native engines were reused. The external fixture supplies
synthetic Neoxa-shaped price data; it is not live market API acceptance.
Existing restore fences remain. No installer or production activation is
included. StartOS wiring and acceptance remain later work.
