# 0102c native package manifest correction

The controller manifest omitted `emulateMissingAs`; the pinned SDK 2.0.9
therefore chose `x86_64` emulation. The native-only package check correctly
refused that setting after packing. This revision adds explicit `null` in the
controller's packaging overlay and checks every input image before packing.
The packed-image policy remains strict: exact image set, native x86_64 only,
packed source, and emulation disabled.

The audit also found that StartOS moves dependency titles/icons out of the
manifest into `dependencies/<id>/metadata.json` and `icon.svg`. Those embedded
files are now verified separately; the required dependency, description and
optional flag must still match exactly. The icon digest is pinned to the exact
source commit already specified in both node manifests. Packed manifests are
saved before checking so diagnostics include the observed fields.

On the packaging VM, resume the original completed 0102a test run:

```bash
cd "$HOME/code/cln-blake/patches" &&
unzip 0102c-package-manifest.zip &&
bash 0102c-package-manifest/test.sh \
  /tmp/privkeyio-0100-results.l8yon5ti \
  --resume-pack /tmp/privkeyio-0102a-results.feqodmkk
```

Keep the original directories. This reuses the completed funded evidence and
exact images, recompiles/verifies handlers, and packs all three installers.
It does not rebuild engines or rerun funded swaps. It leaves the failed 0102b
package available for inspection. The missing-Git-commit message is expected
for these isolated source exports; source trees are recorded separately.

All four source patches remain unchanged. Only packaging preparation and
verification changed. The application versions and grant/payment behavior are
unchanged. Local runner tests and actual SDK manifest checks pass; native
StartOS packing/readback and device acceptance still require the VM/device.

## Retained workspace/resume behavior

The 0102a run completed its gates and reached `s9pk pack`, which refused its
temporary `/tmp` context because it was outside a StartOS packaging workspace.
0102b puts build contexts under the persistent migration workspace, initializes
that workspace through `start-cli s9pk init-workspace`, and reuses an existing
nearest workspace/signing key when present. Existing signing keys must remain
unchanged. The workspace guide/key are outside the exported package sources and
diagnostics. This uses the standard StartOS workspace mechanism:
https://docs.start9.com/packaging/0.4.0.x/environment-setup.html

For the reported failure, download/transfer this bundle as usual, then run on
the packaging VM:

```bash
cd "$HOME/code/cln-blake/patches" &&
unzip 0102c-package-manifest.zip &&
bash 0102c-package-manifest/test.sh \
  /tmp/privkeyio-0100-results.l8yon5ti \
  --resume-pack /tmp/privkeyio-0102a-results.feqodmkk
```

Retain both result directories. Resume validates the original raw test receipts,
progress, source, compiled handlers, six runtime images and funded harness.
It recompiles handlers using the same pinned compiler/dependencies and requires
exact equality with the handlers used by the completed tests. It then reuses
the immutable images and completed six-swap/four-payment gate evidence, packs
all three installers and checks their contents. It does not rebuild engines or
repeat funded tests. The original run stays intact; packaging uses a fresh
export so its partially bound controller manifest is handled correctly.

Results now live below
`~/code/cln-blake/privkeyio-migration/build-results/privkeyio-0102c-results.*`.
The build receipt identifies the original run and explicitly records that its
funded tests were reused. Native StartOS packaging and host acceptance still
need to complete on the VM/device. No local Docker or `start-cli` run is claimed.

The source patches, source-tree pins, installed versions, provenance validators,
compiled runtime and funded acceptance requirements are unchanged from 0102a.
To perform a full run instead, omit `--resume-pack` and its path.

## Retained 0102a receipt correction

The 0102 runner skipped the `compiled_0094` envelope while locating the accepted
0090b XBT node/UI receipt. This correction fixes preflight, the old-engine
bootstrap lookup and the later packaging lookup through one shared selector.
It adds six metadata regression tests and keeps all four source patches,
source-tree pins, prior provenance validators and funded acceptance gates exact.

Rerun directly after the reported 0102 preflight failure. Already-applied 0102
source is accepted; no reset, stash or manual patch reversal is needed. Retain
the original 0100 results as the input; the failed 0102 log directory is not a
replacement for those results.

Apply only to the synced, annotated 0101 migration checkpoint. The runner checks
all four repositories before changing source. That source-patch step does not
commit, reset, stash, fetch, change branches or touch a live node. A repeated run accepts exactly the
before or after tree. Other edits stop the run and remain intact.

On the packaging VM:

```bash
cd "$HOME/code/cln-blake/patches"
unzip 0102c-package-manifest.zip
bash 0102c-package-manifest/test.sh /tmp/privkeyio-0100-results.l8yon5ti
```

Keep the 0100 results/build contexts and their accepted Docker images. The default
workspace is `~/code/cln-blake/privkeyio-migration`. An optional second argument
sets that workspace. The runner reuses exact verified engines, retains the XBT UI,
compiles installed handlers with locked dependencies, runs policy/SDK and funded
regtest gates, and then packs and inspects all three installers. Docker, Git,
Python >=3.12, start-cli and unsquashfs are required. Network access is needed only
for workspace initialization, pinned compiler/UI pulls, npm's lockfile dependencies and BTC OS utilities.

Installers are released together only after all checks pass. Check the printed
output directory and SHA256SUMS; StartOS host acceptance is still pending.
Build receipts retain source milestone `0102` and record runner revision `0102c`.

XBT :2 may update the accepted privkeyio :1 node on its existing volume. The
fresh-install-only BTC and controller branches require dedicated test services.
Do not replace the installed legacy BTC coordinator/controller with these files.
No old experimental XBT wallet import is provided. See TEST-STARTOS.md.

Ordinary restarts and updates preserve state. Backup restoration is a different
recovery workflow and does not preserve usable channels. The runner never opens,
closes, restores or funds a live channel.
