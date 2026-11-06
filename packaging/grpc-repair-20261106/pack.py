from pathlib import Path
import subprocess,json,os,hashlib,importlib.util,shutil
O=Path(__file__).resolve().parent;R=O.parents[1];C=O/'xbt-cln-startos';B=R.parent/'patches/0102c-package-manifest';OLD=R/'build-results/privkeyio-0102c-results.uf22u5mp'
def run(args,**kw):return subprocess.check_output([str(x) for x in args],text=True,**kw)
def logged(args,name,cwd=None):
 with (O/name).open('w') as f:subprocess.run([str(x) for x in args],stdout=f,stderr=subprocess.STDOUT,cwd=cwd,check=True)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
import sys
sys.path.insert(0,str(B))
spec=importlib.util.spec_from_file_location('original',B/'run.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
image=(O/'image.id').read_text().strip();node=json.loads((OLD/'compiled.json').read_text())['node_image']
for name in ['README.md','instructions.md','Dockerfile.live']:shutil.copy2(R/'xbt-cln-startos'/name,C/name)
cmd=['docker','run','--rm','--network','none','--user',f'{os.getuid()}:{os.getgid()}','-v',f'{C}:/work','-w','/work','--entrypoint','node',node]
logged(cmd+['compile.cjs','xbt','pack'],'compile.log')
# CLI 2.7 uses docker save --platform, unavailable in this VM's Docker 26.
# Export immutable images ourselves and use its supported local archive reader.
import tarfile
archive_sources={}
for key,img in [('lightning',image),('ui','sha256:ec6f40ff655888574fc918f33d911ee50602211ed34168e83a50afaa00bb77bd')]:
 archive=O/(key+'-image.tar')
 if not archive.exists():subprocess.run(['docker','image','save','-o',str(archive),img],check=True)
 with tarfile.open(archive) as tar:
  entries=json.load(tar.extractfile('manifest.json'));assert len(entries)==1
  config=tar.extractfile(entries[0]['Config']).read();assert 'sha256:'+hashlib.sha256(config).hexdigest()==img
 archive_sources[key]={'ociLayout':{'path':str(archive)}}
with (C/'javascript/index.js').open('a') as js:
 js.write('\n// Packaging-only local image archives, verified against immutable image IDs.\n')
 for key,source in archive_sources.items():js.write('module.exports.manifest.images['+json.dumps(key)+'].source='+json.dumps(source)+';\n')
(O/'archive-sources.json').write_text(json.dumps(archive_sources,indent=2))

logged(cmd+['scripts/test-package.cjs'],'package-tests.log')
checker=O/'check-installed.cjs';checker.write_text((B/'check-installed.cjs').read_text().replace("xbt:'#privkeyio:26.6.9:2'","xbt:'#privkeyio:26.6.9:3'").replace("'=#privkeyio:26.6.9:1 || =#privkeyio:26.6.9:2'","'=#privkeyio:26.6.9:1 || =#privkeyio:26.6.9:2 || =#privkeyio:26.6.9:3'"))
logged(['node',checker,'xbt',C/'javascript/index.js'],'installed-registry.log')
manifest=json.loads(run(['node','-e','console.log(JSON.stringify(require("./javascript/index.js").manifest))'],cwd=C));(O/'input-manifest.json').write_text(json.dumps(manifest,indent=2))
inv=m.inspect(image,'xbt');prior=json.loads((OLD/'inventories.json').read_text())['xbt-a']
assert inv['runtime']==prior['runtime']
expected=dict(prior['native']);expected['libexec/c-lightning/plugins/cln-grpc']={'sha256':'0b4774e23b8eb81e79fabc0602a43cc53bac962fe229533098b258fd72a4ae06','executable':True}
assert inv['native']==expected
(O/'inventory.json').write_text(json.dumps(inv,indent=2))
assert json.loads((O/'smoke-result.json').read_text())['grpc_plugin_active']
m.public(C/'javascript');m.public(C/'assets')
out=R/'installers/grpc-repair-20261106';out.mkdir(exist_ok=True);package=out/'xbt-cln_x86_64.s9pk'
logged(['start-cli','s9pk','pack','--arch=x86_64','-o',package],'pack.log',C)
packed=json.loads(run(['start-cli','s9pk','inspect',package,'manifest']));(O/'packed-manifest.json').write_text(json.dumps(packed,indent=2))
checks=m.module(B/'package-checks.py','checks')
# The packer parenthesizes a three-way OR. Accept only this exact equivalent
# equality-only expression; keep both original manifests for inspection.
normalized=dict(packed)
if packed['canMigrateFrom'] != manifest['canMigrateFrom']:
 assert packed['canMigrateFrom']=='(=#privkeyio:26.6.9:1 || =#privkeyio:26.6.9:2) || =#privkeyio:26.6.9:3'
 assert manifest['canMigrateFrom']=='=#privkeyio:26.6.9:1 || =#privkeyio:26.6.9:2 || =#privkeyio:26.6.9:3'
 normalized['canMigrateFrom']=manifest['canMigrateFrom']
checks.packed_manifest(normalized,manifest,'xbt')
for dep,row in manifest['dependencies'].items():
 metadata=O/(dep+'-metadata.json');icon=O/(dep+'-icon.svg');m.binary_member(package,'dependencies/'+dep+'/metadata.json',metadata);m.binary_member(package,'dependencies/'+dep+'/icon.svg',icon);checks.dependency_files(row,json.loads(metadata.read_text()),sha(icon))
js=O/'javascript.squashfs';m.binary_member(package,'javascript.squashfs',js);assert m.squash_hash(js,'index.js')==sha(C/'javascript/index.js')
sq=O/'runtime.squashfs';m.binary_member(package,'images/x86_64/lightning.squashfs',sq)
for key,prefix in [('native','opt/xbt/'),('runtime','usr/local/libexec/swap-node/')]:
 for rel,row in inv[key].items():
  if 'sha256' in row:assert m.squash_hash(sq,prefix+rel)==row['sha256'],rel
ui='sha256:ec6f40ff655888574fc918f33d911ee50602211ed34168e83a50afaa00bb77bd';uisq=O/'ui.squashfs';m.binary_member(package,'images/x86_64/ui.squashfs',uisq)
for path,h in m.file_hashes(ui,'/app/apps','node').items():assert m.squash_hash(uisq,path)==h,path
receipt=dict(version=manifest['version'],sha256=sha(package),inputs=json.loads((O/'inputs.json').read_text()),runtime_image=image,checks=['full_typecheck','package_regressions','installed_registry','original_runtime_and_native_bytes_preserved','grpc_source_equality','regtest_startup_restart','packed_manifest','packed_javascript','packed_native_and_runtime','packed_ui'],live_StartOS_acceptance=False,funded_swaps_rerun=False,results=str(O))
(out/'build-receipt.json').write_text(json.dumps(receipt,indent=2));(out/'SHA256SUMS').write_text(''.join(sha(out/name)+'  '+name+'\n' for name in ['xbt-cln_x86_64.s9pk','build-receipt.json']))
print(json.dumps(receipt,indent=2))
