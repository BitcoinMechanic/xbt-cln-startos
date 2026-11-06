# 0101 — checkpoint the accepted StartOS action integration

This checkpoints the exact 0100 sources and actual test evidence reported at
`/tmp/privkeyio-0100-results.l8yon5ti`. It does not rebuild, rerun payments, install,
restart or modify a live node. Keep the complete 0100 results directory, including
its build context, until the source export has succeeded.

On the packaging VM, after extracting this bundle into your normal patches folder:

```bash
bash "$HOME/code/cln-blake/patches/0101-privkeyio-actions-checkpoint/export-vm.sh"
```

The exporter validates the four exact source trees, annotated 0099 checkpoint
ancestry, original raw receipts, compiled handlers and harness inputs. It requires
all six funded cases, SDK action coverage and retained engine/runtime provenance.
The exported ZIP contains source patches and validation records; it excludes
wallets, journals, credentials, certificates and raw payment logs.

Expected export:

```text
~/code/cln-blake/privkeyio-migration/checkpoints/privkeyio-startos-actions-20261014/source-export.zip
```

Copy that ZIP to the tower and extract it in a fresh directory. Run
`checkpoint-tower.sh` from the **VM-exported** `0101-privkeyio-actions-checkpoint`
folder. It defaults to your existing clones in `~/code/cln-blake` and creates
detached worktrees under `~/tmp/cln-privkeyio-actions-checkpoint`. It accepts the
suffixless lightning origin and preserves the existing checkouts, staged work
and credentials. No new large clone is needed.

After all four pushes succeed, run on the packaging VM:

```bash
bash "$HOME/code/cln-blake/patches/0101-privkeyio-actions-checkpoint/sync-vm.sh"
```

The sync checks all remote branches/tags before stashing, then fast-forwards the
migration branches. Existing and new stashes remain saved. Do not pop them onto
the already-applied checkpoint. The scripts support resuming a partial push or
an interrupted stash-before-merge operation; they never force-push.

All four repositories receive the annotated tag
`privkeyio-startos-actions-20261014`. Default branches are unchanged.

`--results-dir PATH` overrides the saved 0100 result path for export.
`--cache-root PATH` selects a different existing tower clone parent. An optional
positional root selects the migration workspace or detached-worktree parent.

The accepted scope is regtest SDK integration. Installed action registries and
live startup are unchanged. No StartOS host installation/upgrade acceptance is
claimed. Checkpointing preserves that distinction in the exported evidence.
