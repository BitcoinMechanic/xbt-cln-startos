# Retained integration packaging tools

This directory preserves the build tools and selected verification records for
the live integration candidate and its XBT startup repair. The application
sources are in the four migration branches; installers and Docker images remain
on the packaging VM. No wallet data, pairing credentials or raw payment logs are
included here.

## 0102c runner

`0102c/` is a checksum-verified, unchanged copy of the original bundle. Its
`SHA256SUMS` covers the bundled files. The source manifest describes the 0101
checkpoint plus the original 0102 worktrees, not later committed checkpoints.

The full/resume runner requires authentic 0100 raw inputs that were originally
stored in `/tmp` and are no longer available on the VM. Retained aggregate
receipts alone do not satisfy those checks. Do not fabricate receipts or bypass
source/evidence checks to run it against this newer checkpoint.

## XBT gRPC startup repair

`grpc-repair-20261106/` retains the scripts and selected records from the repair
that produced package `#privkeyio:26.6.9:3`. Its `build-receipt.json` binds the
installer, compiler, runtime and input images. `host-report.json` records the
user's subsequent host observations separately from the build-time receipt.

The original 0102 runtime omitted gRPC, and the retained daemon's compiled
builtin-plugin list did not automatically load either gRPC or CLNrest. The
repair adds the previously accepted gRPC binary and explicitly loads both
plugins. The donor's Rust crate sources and Cargo lockfile match the current
engine checkout. Original daemon, other native files, swap runtime and UI bytes
were checked unchanged, including readback from the final installer.

These scripts are archived from the successful VM results directory, not a
self-contained clean-checkout build entry point. They expect the original
layout under `~/code/cln-blake/privkeyio-migration`, including the retained
`build-results/privkeyio-0102c-results.uf22u5mp` context and exact images. The
repair context is `build-results/grpc-repair-20261106`; `image.id` and the
image archives remain there. `pack.py` imports the original runner from
`~/code/cln-blake/patches/0102c-package-manifest` for content verification.
Inspect those prerequisites before rerunning; the pack script writes its output
and receipt. `SHA256SUMS` in the repair directory describes the original
installer transfer set, including artifacts retained on the VM rather than in
Git, and is not a checksum list for this source directory.

The repair used CLI 2.7.0 with the original SDK 2.0.9, TypeScript 6.0.3, ncc
0.38.4 and pinned Node compiler image. Docker 26 lacks `image save --platform`,
so the runner exports ordinary local image archives, verifies each image-config
digest, and uses the CLI's local archive reader. Its packaging-only JavaScript
overlay binds those archives without changing installed action behavior.

Verification covers generated configuration, disposable regtest startup and
same-volume restart, migration guards and journal preservation, compilation,
installed actions, and packed manifest/JavaScript/native/runtime/UI contents.
The user subsequently confirmed startup, UI access and `CHANNELD_NORMAL`.
This checkpoint does not claim a live payment, complete identity/funding
comparison, or routed swap acceptance. BTC/controller host acceptance is also
pending; inspect BTC's corresponding plugin/configuration integration before
installing it.
