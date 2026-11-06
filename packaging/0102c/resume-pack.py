"""Verify completed 0102 gates and immutable images before packaging resumes."""
import json,shutil
from pathlib import Path


def file(root,rel):
    path=Path(rel)
    if path.is_absolute() or '..' in path.parts:raise RuntimeError('Unsafe retained path')
    p=root/path
    if not p.is_file() or any(v.is_symlink() for v in (p,*p.parents)):
        raise RuntimeError('Missing or symlinked retained input: '+str(p))
    return p


def read(root,rel):return json.loads(file(root,rel).read_text())


def completed_gates(r,saved,e,inv):
    gates=read(saved,'gates.json')
    r.need(type(gates) is dict and set(gates)=={'units','swaps','actions','bootstrap'},'Incomplete retained gate set')
    r.same(gates['units'],dict(tests=184,failures=0,errors=0,skipped=0),'Retained unit acceptance differs')
    r.same(read(saved,'checks/unit-result.json'),gates['units'],'Raw unit result differs')
    r.module(r.B/'validate-package-result.py','resume_packages').validate(gates['swaps'])
    r.module(r.B/'validate-actions.py','resume_actions').validate(gates['actions'])
    r.same(gates['bootstrap'],r.bootstrap_expected(e,inv),'Retained bootstrap evidence differs')
    paths=['gates.json','checks/unit-result.json']
    for suite,receipts in [('matrix',{'package-result.json':'swaps','action-result.json':'actions'}),
                           ('bootstrap',{'bootstrap-result.json':'bootstrap'})]:
        runs=list((saved/suite).glob('privkeyio-0066-*'))
        r.need(len(runs)==1,'Expected one retained '+suite+' run')
        progress=str(runs[0].relative_to(saved)/'progress.json')
        r.same(read(saved,progress),dict(stage='complete'),'Retained '+suite+' did not complete');paths.append(progress)
        for name,key in receipts.items():
            rel=str(runs[0].relative_to(saved)/name)
            r.same(read(saved,rel),gates[key],'Raw retained '+key+' differs');paths.append(rel)
    for name in ('units','sdk-regression','sdk-live','synthetic','matrix','bootstrap'):
        rel=name+'.log';r.need(file(saved,rel).stat().st_size>0,'Missing completed gate log: '+name);paths.append(rel)
    return gates,paths


def verify(r,saved,root,context,results,e,source):
    r.need(saved.is_dir() and not any(p.is_symlink() for p in (saved,*saved.parents)),
           'Original completed result directory required')
    r.need(saved!=results,'Cannot resume from current output')
    r.same(read(saved,'retained-0100.json'),e,'Retained 0100 provenance changed')
    r.same(read(saved,'source.json'),source,'Completed tests used different source')
    compiled=read(saved,'compiled.json')
    r.same(compiled,r.load(results/'compiled.json'),'Recompiled handlers differ from the completed tests')
    images=read(saved,'images.json');inv=read(saved,'inventories.json')
    keys={a+'-'+g for a in r.REPOS for g in ('a','b')}
    r.need(type(images) is dict and set(images)==keys and set(inv)==keys,'Six retained runtime images required')
    gates,paths=completed_gates(r,saved,e,inv)
    oldcontext=saved/'build-context'
    # The failed pack may already have bound a manifest to exact image IDs.
    btcui=r.pull(r.BTC_UI,results,'btc-ui')
    uis={'btc':btcui,'xbt':r.old_candidate(e)['images']['ui']}
    verify_source_inputs(r,oldcontext,context,source,images,uis)
    for asset,repo in r.REPOS.items():
        r.same(read(oldcontext,repo+'/compile-result.json'),compiled['receipts'][asset],'Original compiler receipt differs')
        r.need(r.cp.digest(file(oldcontext,repo+'/compile.cjs'))==r.cp.digest(r.B/'compile.cjs'),'Original compiler driver differs')
        for phase in ('regression','live'):
            r.same(r.inventory(oldcontext/repo/phase),compiled['files'][asset][phase],'Original compiled handlers changed')
    stage=r.module(context/'lightning/tools/swap/package_runtime.py','resume_stage')
    sealed=read(saved,'runtime-manifests.json');r.need(set(sealed)==keys,'Retained runtime manifest set differs')
    staged=results/'verified-runtime-source';staged.mkdir()
    for key,image in images.items():
        asset,generation=key.split('-');role='controller' if asset=='controller' else 'node'
        expected=stage.stage(context/'lightning/tools/swap',context/'swap-controller-startos/migration',staged/key,role,generation,live=True)
        r.same(sealed[key],expected,'Retained runtime source differs: '+key)
        r.tag(image,'resume-'+key)
        observed=r.inspect(image,asset)
        r.same(observed,inv[key],'Retained immutable image inventory differs: '+key)
        r.same(observed['manifest'],expected,'Retained runtime does not match source: '+key)
        if asset!='controller':
            prior=e['retained_0098a']['inventories'][key]
            r.same(observed['native'],prior['native'],'Retained native engine/plugin differs')
            r.same(observed['version'],prior['version'],'Retained native version differs')
    image=file(saved,'image.id').read_text().strip();r.tag(image,'resume-fixture')
    files=read(saved,'harness-files.json')
    r.same(r.inventory(oldcontext/'fixture'),files,'Original funded harness context changed')
    expected={}
    for rel,h in files.items():
        if rel.startswith('swap/'):path='/opt/swap0098/'+rel.removeprefix('swap/')
        elif rel.startswith('controller/'):path='/opt/controller0098/'+rel.removeprefix('controller/')
        elif rel.startswith(('actions0100/','actions0102/')):path='/opt/'+rel
        elif rel=='unit-tests.py':path='/opt/source/unit-tests.py'
        elif rel=='Dockerfile':continue
        else:raise RuntimeError('Unexpected retained harness input: '+rel)
        expected[path]=h
    probe="""import hashlib,json,os,sys
from pathlib import Path
def inventory(root):
 result={}
 for p in sorted(root.rglob('*')):
  if p.is_symlink():result[str(p.relative_to(root))]=dict(link=os.readlink(p))
  elif p.is_file():result[str(p.relative_to(root))]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),executable=bool(p.stat().st_mode&0o111))
 return result
files={p:hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in json.loads(sys.argv[1])}
print(json.dumps(dict(files=files,old_engine=hashlib.sha256(Path('/opt/xbt-before/bin/lightningd').read_bytes()).hexdigest(),
 releases={g:{a:inventory(Path('/opt/releases')/g/a) for a in ('btc','xbt','node','controller')} for g in ('a','b')})))
"""
    observed=json.loads(r.output(r.readonly(image,['python3','-I','-c',probe,json.dumps(list(expected))])))
    r.same(observed['files'],expected,'Funded image source/handlers changed')
    r.same(observed['old_engine'],r.old_candidate(e)['engine_sha256'],'Pre-update XBT engine differs')
    extracted=read(saved,'extracted.json');r.same(observed['releases'],extracted,'Funded image release files differ')
    for g in ('a','b'):
        wanted={a:inv[a+'-'+g]['native'] for a in ('btc','xbt')}
        wanted.update(node=inv['btc-'+g]['runtime'],controller=inv['controller-'+g]['runtime'])
        r.same(extracted[g],wanted,'Funded image/runtime binding differs')
    # Preserve the original run and copy only public build/test evidence.
    paths+=['images.json','inventories.json','runtime-manifests.json','image.id','harness-files.json','extracted.json']
    hashes={}
    for rel in paths:
        p=file(saved,rel);target=results/rel;target.parent.mkdir(parents=True,exist_ok=True)
        r.need(not target.exists(),'Existing resume output retained: '+rel)
        shutil.copyfile(p,target);hashes[rel]=r.cp.digest(p)
    for rel in ('source.json','compiled.json','retained-0100.json'):hashes[rel]=r.cp.digest(file(saved,rel))
    shutil.copytree(oldcontext/'fixture',context/'fixture')
    r.save(results/'resume.json',dict(original_results=str(saved),original_fixture_image=image,
        original_receipts_sha256=hashes,funded_tests_reused=True,funded_tests_rerun=False,
        native_engines_rebuilt=False,source_and_images_reverified=True))
    print('PASS: original six swaps and four bootstrap payments revalidated; exact images reused; packaging resumes.',flush=True)
    return images


def verify_source_inputs(r,oldcontext,context,source,images,uis):
    manifests={repo+'/startos/manifest/index.ts':asset for asset,repo in r.REPOS.items()}
    for rel,wanted in source['files'].items():
        p=file(oldcontext,rel)
        if r.cp.digest(p)==wanted:continue
        r.need(rel in manifests,'Retained source input changed: '+rel)
        asset=manifests[rel]
        original=(context/rel).read_text()
        expected={r.bound_manifest_text(original,asset,images[asset+'-a'],uis.get(asset)),
                  r.packaging_manifest_text(original,asset,images[asset+'-a'],uis.get(asset))}
        r.need(p.read_text() in expected,'Retained manifest has an unexpected change: '+rel)
