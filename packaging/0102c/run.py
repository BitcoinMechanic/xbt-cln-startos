#!/usr/bin/env python3
"""Exact-source candidate build; funded regtest gates precede installer release."""
import argparse,hashlib,importlib.util,io,json,os,re,shutil,subprocess,sys,tarfile,tempfile,zipfile
from pathlib import Path
import common as cp
B=Path(__file__).resolve().parent
TAG=cp.TAG
RUNNER_REVISION='0102c'
NODE='node:22-bookworm@sha256:8a34c4ab3ea2c5cd194f07e317b2a8f09461d3c8b05c4e34c8ccd56d56024c4d'
BTC_UI='ghcr.io/elementsproject/cln-application:26.09@sha256:27684e8e495d077ce661793f74b25d50c2e40f68552cb1ba57d6750dd2585798'
REPOS={'controller':'swap-controller-startos','btc':'btc-cln-startos','xbt':'xbt-cln-startos'}
IDS={'btc':'c-lightning','xbt':'xbt-cln','controller':'swap-controller'}
VERSIONS={'btc':'#privkeyio:26.6.9:0','xbt':'#privkeyio:26.6.9:2','controller':'#privkeyio:0.1.0:0'}
def need(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):need(json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True),why)
def load(p):return json.loads(p.read_text())
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def output(command,*,cwd=None,timeout=180):
    p=subprocess.run(list(map(str,command)),cwd=cwd,capture_output=True,text=True,timeout=timeout)
    need(p.returncode==0,'Command failed: '+str(command[0])+'; '+p.stderr[-1500:]);return p.stdout.strip()
def logged(command,path,*,cwd=None):
    with path.open('w') as log:
        p=subprocess.Popen(list(map(str,command)),cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        for line in p.stdout:sys.stdout.write(line);sys.stdout.flush();log.write(line);log.flush()
        need(p.wait()==0,'Command failed; inspect '+str(path))
def module(path,name):
    s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def image_id(v):return type(v) is str and re.fullmatch(r'sha256:[a-f0-9]{64}',v) is not None
def tag(image,label):
    need(image_id(image),'Immutable image required')
    row=json.loads(output(['docker','image','inspect',image]))[0]
    need(row['Id']==image and row['Os']=='linux' and row['Architecture']=='amd64','Accepted native image missing')
    name='swap0102-'+label+':'+image[7:]
    p=subprocess.run(['docker','image','inspect','--format','{{.Id}}',name],capture_output=True,text=True)
    need(p.returncode!=0 or p.stdout.strip()==image,'Conflicting local tag retained')
    output(['docker','tag',image,name]);return name
def pull(reference,results,label):
    need('@sha256:' in reference,'Digest-pinned image required')
    p=subprocess.run(['docker','image','inspect','--format','{{.Id}}',reference],capture_output=True,text=True)
    if p.returncode:logged(['docker','pull',reference],results/(label+'-pull.log'))
    return output(['docker','image','inspect','--format','{{.Id}}',reference])
def readonly(image,command):
    return ['docker','run','--rm','--network','none','--read-only','--cap-drop','ALL','--security-opt','no-new-privileges',
            '--user',str(os.getuid())+':'+str(os.getgid()),'--entrypoint',command[0],image,*command[1:]]
def inventory(path):
    result={}
    for p in sorted(path.rglob('*')):
        need(not p.is_symlink(),'Generated symlink refused')
        if p.is_file():result[str(p.relative_to(path))]=cp.digest(p)
    return result
def public(path):
    for p in (path,*path.rglob('*')):
        need(not p.is_symlink(),'Public build-context symlink refused')
        p.chmod(0o755 if p.is_dir() or p.stat().st_mode&0o111 else 0o644)
def inspect(image,role):
    return json.loads(output(readonly(image,['python3','-B','-I','-c',(B/'image-inspect.py').read_text(),role])))
def packaging_workspace(root,results):
    # Build contexts must be descendants of the persistent workspace so the
    # CLI finds the same guide/config/signing key on every run.
    workspace=next((p for p in (root,*root.parents) if (p/'.startos/build.key.pem').is_file()),root)
    key=workspace/'.startos/build.key.pem'
    before=cp.digest(key) if key.is_file() else None
    logged(['start-cli','s9pk','init-workspace'],results/'workspace-init.log',cwd=workspace)
    need(key.is_file(),'Packaging workspace signing key missing after initialization')
    if before is not None:need(cp.digest(key)==before,'Existing workspace signing key changed')
    save(results/'workspace.json',dict(path=str(workspace),existing_key_preserved=before is not None,
                                     start_cli=output(['start-cli','--version'])))
    return workspace
def contexts(root,context,results):
    spec=load(B/'source-manifest.json');files={}
    for name,s in spec.items():
        target=context/name;target.mkdir()
        names=cp.git(root/name,'ls-tree','-r','--name-only',s['tree']).splitlines()
        for rel in names:
            wanted=(name=='lightning' and rel.startswith('tools/swap/') and rel.endswith('.py')) or (name!='lightning')
            if not wanted:continue
            mode=cp.git(root/name,'ls-tree',s['tree'],'--',rel).split()[0]
            if mode=='160000':continue
            need(mode in ('100644','100755'),'Tracked source symlink refused: '+rel)
            raw=subprocess.check_output(['git','-C',str(root/name),'show',s['tree']+':'+rel])
            need(cp.ordinary_path(root/name,rel).read_bytes()==raw,'Source changed during export: '+rel)
            dest=target/rel;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw);dest.chmod(int(mode[-3:],8))
            files[name+'/'+rel]=hashlib.sha256(raw).hexdigest()
    source=dict(schema=1,milestone='0102',base_tag=TAG,base_commits={n:cp.git(root/n,'rev-parse','HEAD') for n in spec},
                trees={n:s['tree'] for n,s in spec.items()},files=files)
    save(results/'source.json',source);return source

def compile_actions(context,results,node):
    compiled={};receipts={}
    for asset,repo in REPOS.items():
        cwd=context/repo;shutil.copyfile(B/'compile.cjs',cwd/'compile.cjs')
        logged(['docker','run','--rm','--cap-drop','ALL','--security-opt','no-new-privileges','--user',f'{os.getuid()}:{os.getgid()}',
            '--workdir','/work','--mount',f'type=bind,src={cwd},dst=/work','--entrypoint','node',node,'compile.cjs',asset],results/(asset+'-compile.log'))
        receipts[asset]=load(cwd/'compile-result.json')
        need(receipts[asset]['full_typecheck'] and receipts[asset]['sdk']=='2.0.9','Compiler check missing')
        compiled[asset]={k:inventory(cwd/k) for k in ('regression','live')}
    save(results/'compiled.json',dict(node_image=node,receipts=receipts,files=compiled));return compiled

def runtime_images(context,results,e):
    old=e['retained_0098a'];base=tag(e['image'],'accepted-fixture')
    stage=module(context/'lightning/tools/swap/package_runtime.py','stage0102')
    images={};observed={};manifests={}
    for generation in ('a','b'):
        for asset in ('btc','xbt','controller'):
            key=asset+'-'+generation;cwd=context/key;cwd.mkdir();role='controller' if asset=='controller' else 'node'
            manifests[key]=stage.stage(context/'lightning/tools/swap',context/'swap-controller-startos/migration',cwd/'runtime',role,generation,live=True)
            parent=old['images'][key];same(inspect(parent,asset),old['inventories'][key],'Prior runtime inventory differs')
            parent_tag=tag(parent,key)
            shutil.copyfile(context/REPOS[asset]/'Dockerfile.live',cwd/'Dockerfile');public(cwd)
            logged(['docker','build','--pull=false','--progress=plain','--build-arg','PARENT_IMAGE='+parent_tag,
                '--build-arg','CLI_IMAGE='+base,'--iidfile',results/(key+'.id'),cwd],results/(key+'-build.log'))
            images[key]=(results/(key+'.id')).read_text().strip();tag(images[key],'built-'+key)
            observed[key]=inspect(images[key],asset)
            same(observed[key]['manifest'],manifests[key],'Sealed runtime differs')
            if asset!='controller':
                same(observed[key]['native'],old['inventories'][key]['native'],'Accepted engine/plugin bytes changed')
                same(observed[key]['version'],old['inventories'][key]['version'],'Engine version changed')
                output(readonly(images[key],['bitcoin-cli','--version']))
    save(results/'images.json',images);save(results/'inventories.json',observed);save(results/'runtime-manifests.json',manifests)
    return images,observed

def old_candidate(e):
    # 0094a wraps the original compiled 0094 receipt. Its historical evidence
    # is 0092a, whose historical evidence is 0091 and contains the 0090b build.
    # prior-check.py validates this complete chain before any build uses it.
    path=('retained_0098a','prior_0096a','prior_0094a','compiled_0094',
          'historical_evidence','historical_evidence','candidate_build')
    row=e
    for position,key in enumerate(path):
        need(type(row) is dict and key in row,
             'Retained 0090b build receipt missing at '+'.'.join(path[:position+1]))
        row=row[key]
    need(type(row) is dict and row.get('milestone')=='0090b',
         'Expected the retained 0090b build receipt')
    return row

def harness(context,results,e,images):
    cwd=context/'fixture';cwd.mkdir()
    for phase,path in [('regression','actions0100'),('live','actions0102')]:
        dest=cwd/path;dest.mkdir()
        for asset,repo in REPOS.items():shutil.copytree(context/repo/phase,dest/asset)
        scripts=context/'swap-controller-startos/scripts'
        for filename in ('test-migration-actions.cjs','test-live-actions.cjs','migration-action-fixture.cjs','test-migration-process.py'):
            shutil.copyfile(scripts/filename,dest/filename)
        save(dest/'modules.json',{a:f'/opt/{path}/{a}/index.js' for a in REPOS})
    shutil.copytree(context/'lightning/tools/swap',cwd/'swap')
    shutil.copytree(context/'swap-controller-startos/migration',cwd/'controller')
    shutil.copyfile(B/'unit-tests.py',cwd/'unit-tests.py')
    lines=[f'FROM {tag(i,"harness-"+k)} AS {k}' for k,i in images.items()]
    lines += [f'FROM {tag(old_candidate(e)["images"]["node"],"accepted-node-before")} AS nodebefore',
        f'FROM {tag(e["image"],"harness-base")}',
        'COPY --from=nodebefore /usr/local/ /opt/xbt-before/',
        'RUN rm -rf /opt/swap0098 /opt/controller0098 /opt/actions0100 /opt/actions0102 /opt/releases/a/node /opt/releases/b/node /opt/releases/a/controller /opt/releases/b/controller',
        'COPY swap/ /opt/swap0098/','COPY controller/ /opt/controller0098/',
        'COPY swap/ /opt/source/lightning/tools/swap/','COPY controller/ /opt/source/swap-controller-startos/migration/',
        'ENV PYTHONPATH=/opt/swap0098:/opt/controller0098', 'COPY unit-tests.py /opt/source/unit-tests.py','COPY actions0100/ /opt/actions0100/','COPY actions0102/ /opt/actions0102/']
    for g in ('a','b'):
        for a in ('btc','xbt'):lines += [f'COPY --from={a}-{g} /opt/{a}/ /opt/releases/{g}/{a}/']
        lines += [f'COPY --from=btc-{g} /usr/local/libexec/swap-node/ /opt/releases/{g}/node/',
                  f'COPY --from=controller-{g} /usr/local/libexec/swap-controller/ /opt/releases/{g}/controller/']
    lines += ['RUN rm -rf /usr/local/libexec/swap-node /opt/btc /opt/xbt',
        'COPY --from=btc-a /usr/local/libexec/swap-node/ /usr/local/libexec/swap-node/',
        'COPY --from=btc-a /opt/btc/ /opt/btc/','COPY --from=xbt-a /opt/xbt/ /opt/xbt/']
    (cwd/'Dockerfile').write_text('\n'.join(lines)+'\n');public(cwd)
    logged(['docker','build','--pull=false','--network=none','--progress=plain','--iidfile',results/'image.id',cwd],results/'harness-build.log')
    image=(results/'image.id').read_text().strip();tag(image,'harness')
    code="""import hashlib,json,os
from pathlib import Path
def inv(root):
 r={}
 for p in sorted(root.rglob('*')):
  if p.is_symlink():r[str(p.relative_to(root))]=dict(link=os.readlink(p))
  elif p.is_file():r[str(p.relative_to(root))]=dict(sha256=hashlib.sha256(p.read_bytes()).hexdigest(),executable=bool(p.stat().st_mode&0o111))
 return r
print(json.dumps({g:{k:inv(Path('/opt/releases')/g/k) for k in ('btc','xbt','node','controller')} for g in ('a','b')}))
"""
    extracted=json.loads(output(readonly(image,['python3','-I','-c',code])))
    inv=load(results/'inventories.json')
    for g in ('a','b'):
        for a in ('btc','xbt'):same(extracted[g][a],inv[a+'-'+g]['native'],'Harness engine differs')
        same(extracted[g]['node'],inv['btc-'+g]['runtime'],'Harness node runtime differs')
        same(extracted[g]['controller'],inv['controller-'+g]['runtime'],'Harness controller runtime differs')
    oldhash=output(readonly(image,['python3','-I','-c',"import hashlib;from pathlib import Path;print(hashlib.sha256(Path('/opt/xbt-before/bin/lightningd').read_bytes()).hexdigest())"]))
    need(oldhash==old_candidate(e)['engine_sha256'],'Prior installed XBT engine changed')
    save(results/'extracted.json',extracted);save(results/'harness-files.json',inventory(cwd));return image

def gates(root,results,image,e):
    checks=results/'checks';checks.mkdir()
    for name,command in [
        ('units',['python3','/opt/source/unit-tests.py','/opt/source','--receipt','/checks/unit-result.json']),
        ('sdk-regression',['node','--no-deprecation','/opt/actions0100/test-migration-actions.cjs','/opt/actions0100/modules.json']),
        ('sdk-live',['node','--no-deprecation','/opt/actions0102/test-live-actions.cjs','/opt/actions0102/modules.json']),
        ('synthetic',['python3','/opt/actions0100/test-migration-process.py','/opt/actions0100','/opt/swap0098','/opt/controller0098'])]:
        args=readonly(image,command);args[3:3]=['--tmpfs','/tmp:rw,nosuid,nodev,size=256m','--mount',f'type=bind,src={checks},dst=/checks']
        logged(args,results/(name+'.log'))
    units=load(checks/'unit-result.json');same(units,dict(tests=184,failures=0,errors=0,skipped=0),'All unit gates required without skips')
    receipts=dict(units=units)
    for suite,script in [('matrix','test_startos_actions.py'),('bootstrap','test_live_bootstrap.py')]:
        directory=results/suite;directory.mkdir();name='swap0102-'+suite+'-'+os.urandom(5).hex()
        args=['docker','run','--rm','--name',name,'--network','none','--init','--read-only','--cap-drop','ALL',
            '--security-opt','no-new-privileges','--pids-limit','512','--user',f'{os.getuid()}:{os.getgid()}',
            '--tmpfs','/tmp:rw,nosuid,nodev,size=512m','--env','TOKIO_WORKER_THREADS=2',
            '--mount',f'type=bind,src={root.parent}/bitcoind,dst=/test-bitcoind,readonly',
            '--mount',f'type=bind,src={directory},dst=/results','--entrypoint','python3',image,
            '/opt/swap0098/'+script,'--disposable-regtest','--btc-prefix','/opt/btc','--xbt-prefix','/opt/xbt',
            '--bitcoind','/test-bitcoind','--bitcoin-cli','/usr/bin/bitcoin-cli','--results-parent','/results']
        try:logged(args,results/(suite+'.log'))
        finally:subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        runs=list(directory.glob('privkeyio-0066-*'));need(len(runs)==1,'Expected one '+suite+' run')
        same(load(runs[0]/'progress.json'),dict(stage='complete'),suite+' incomplete')
        if suite=='matrix':
            receipts['swaps']=load(runs[0]/'package-result.json');module(B/'validate-package-result.py','packages').validate(receipts['swaps'])
            receipts['actions']=load(runs[0]/'action-result.json');module(B/'validate-actions.py','actions').validate(receipts['actions'])
        else:
            receipts['bootstrap']=load(runs[0]/'bootstrap-result.json')
            inv=load(results/'inventories.json')
            same(receipts['bootstrap'],bootstrap_expected(e,inv),'Bootstrap evidence differs')
    save(results/'gates.json',receipts);return receipts

def bootstrap_expected(e,inv):
    cases=[dict(profile=p,version_before=('v26.06.9-blake2b.7-swap0088b' if a=='xbt' else inv[a+'-a']['version']),
        version_after=inv[a+'-a']['version'],engine_before=(old_candidate(e)['engine_sha256'] if a=='xbt' else inv[a+'-a']['native']['bin/lightningd']['sha256']),
        engine_after=inv[a+'-a']['native']['bin/lightningd']['sha256'],payments=2,original_channel=True,original_identity=True,closed_channels=0,
        repeated_setup_unchanged=True,static_plugins_ready=True,regtest_only=True) for a,p in [('btc','btc-cln-v1'),('xbt','xbt-privkeyio-v1')]]
    return dict(schema=1,fixture='0102-bootstrap',cases=cases)

def bound_manifest_text(text,asset,node,ui=None):
    for filename,image in [('Dockerfile.live',node)]+([('Dockerfile.ui',ui)] if asset=='xbt' else []):
        pattern=r"source: \{\s*dockerBuild: \{\s*dockerfile: '"+re.escape(filename)+r"',\s*workdir: '\.'\s*,?\s*\}\s*,?\s*\}"
        text,count=re.subn(pattern,"source: { dockerTag: '"+image+"' }",text);need(count==1,'Manifest image shape changed: '+asset)
    if asset=='btc':
        need(BTC_UI in text,'BTC UI pin changed');text=text.replace(BTC_UI,ui)
    text=text.replace("arch: ['x86_64', 'aarch64']","arch: ['x86_64']").replace("emulateMissingAs: 'aarch64'",'emulateMissingAs: null')
    return text
def packaging_manifest_text(text,asset,node,ui=None):
    text=bound_manifest_text(text,asset,node,ui)
    if asset=='controller':
        # SDK 2.0.9 defaults an omitted legacy emulation field to x86_64.
        # The candidate is deliberately native x86_64 only, like both nodes.
        need('emulateMissing' not in text,'Controller emulation template changed')
        text,count=re.subn(r"arch: \['x86_64'\]", "arch: ['x86_64'], emulateMissingAs: null",text)
        need(count==1,'Controller image architecture template changed')
    return text
def bind_manifest(context,asset,node,ui=None):
    p=context/'startos/manifest/index.ts';before=cp.digest(p)
    text=packaging_manifest_text(p.read_text(),asset,node,ui)
    p.write_text(text);return dict(before=before,after=cp.digest(p),images=dict(runtime=node,ui=ui))
def binary_member(package,member,target):
    with target.open('wb') as f:
        p=subprocess.run(['start-cli','s9pk','inspect',str(package),'cat',member],stdout=f,stderr=subprocess.PIPE)
    need(p.returncode==0,'Packed member missing: '+member)
def squash_hash(squash,path):
    p=subprocess.Popen(['unsquashfs','-cat',str(squash),path],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    h=hashlib.sha256()
    for chunk in iter(lambda:p.stdout.read(1024*1024),b''):h.update(chunk)
    err=p.stderr.read();need(p.wait()==0,'Packed file missing: '+path);return h.hexdigest()
def file_hashes(image,root,entrypoint):
    # UI accepted full application inventory, not just a version label.
    script=(B/'ui-probe.cjs').read_text()
    return json.loads(output(readonly(image,[entrypoint,'-e',script]),timeout=180))
def pack(root,context,results,e,images,node,source):
    xbtui=old_candidate(e)['images']['ui'];tag(xbtui,'accepted-xbt-ui')
    btcui=pull(BTC_UI,results,'btc-ui');tag(btcui,'btc-ui')
    uis={'btc':btcui,'xbt':xbtui};ui_hashes={a:file_hashes(i,'/app/apps','node') for a,i in uis.items()}
    checks=module(B/'package-checks.py','package_checks')
    receipts={};out=results/'installers-pending';out.mkdir()
    for asset,repo in REPOS.items():
        cwd=context/repo;binding=bind_manifest(cwd,asset,images[asset+'-a'],uis.get(asset))
        logged(['docker','run','--rm','--network','none','--cap-drop','ALL','--security-opt','no-new-privileges','--user',f'{os.getuid()}:{os.getgid()}',
            '--workdir','/work','--mount',f'type=bind,src={cwd},dst=/work','--entrypoint','node',node,'compile.cjs',asset,'pack'],results/(asset+'-pack-compile.log'))
        public(cwd/'javascript')
        logged(['node','--no-deprecation',B/'check-installed.cjs',asset,cwd/'javascript/index.js'],results/(asset+'-installed-registry.log'))
        if (cwd/'assets').is_dir():public(cwd/'assets')
        # The installed registry, not a separate form-only fixture.
        manifest=json.loads(output(['node','-e','console.log(JSON.stringify(require("./javascript/index.js").manifest))'],cwd=cwd))
        need(manifest['id']==IDS[asset] and manifest['version']==VERSIONS[asset],'Compiled package identity differs')
        save(results/(asset+'-input-manifest.json'),manifest)
        wanted={'controller':{'dockerTag':images['controller-a']}} if asset=='controller' else {
            'lightning':{'dockerTag':images[asset+'-a']},'ui':{'dockerTag':uis[asset]}}
        checks.images(manifest,asset,wanted)
        package=out/(IDS[asset]+'_x86_64.s9pk')
        logged(['start-cli','s9pk','pack','--arch=x86_64','-o',package],results/(asset+'-pack.log'),cwd=cwd)
        packed=json.loads(output(['start-cli','s9pk','inspect',package,'manifest']))
        save(results/(asset+'-packed-manifest.json'),packed)
        checks.packed_manifest(packed,manifest,asset)
        for dep,row in manifest['dependencies'].items():
            metadata=results/(asset+'-'+dep+'-metadata.json');icon=results/(asset+'-'+dep+'-icon.svg')
            binary_member(package,'dependencies/'+dep+'/metadata.json',metadata)
            binary_member(package,'dependencies/'+dep+'/icon.svg',icon)
            checks.dependency_files(row,load(metadata),cp.digest(icon))
        js=results/(asset+'-javascript.squashfs');binary_member(package,'javascript.squashfs',js)
        need(squash_hash(js,'index.js')==cp.digest(cwd/'javascript/index.js'),'Packed installed actions differ');js.unlink()
        imagekey='controller' if asset=='controller' else 'lightning';squash=results/(asset+'-runtime.squashfs')
        binary_member(package,'images/x86_64/'+imagekey+'.squashfs',squash)
        inv=load(results/'inventories.json')[asset+'-a'];role='controller' if asset=='controller' else 'node'
        for rel,entry in inv['runtime'].items():
            if 'sha256' in entry:need(squash_hash(squash,'usr/local/libexec/swap-'+role+'/'+rel)==entry['sha256'],'Packed runtime changed: '+rel)
        if asset!='controller':
            for rel,entry in inv['native'].items():
                if 'sha256' in entry:need(squash_hash(squash,'opt/'+asset+'/'+rel)==entry['sha256'],'Packed engine/plugin changed: '+rel)
        squash.unlink()
        if asset in uis:
            squash=results/(asset+'-ui.squashfs');binary_member(package,'images/x86_64/ui.squashfs',squash)
            for path,h in ui_hashes[asset].items():need(squash_hash(squash,path)==h,'Packed UI changed: '+path)
            squash.unlink()
        receipts[asset]=dict(package=package.name,sha256=cp.digest(package),version=VERSIONS[asset],binding=binding,
            compiled_sha256=cp.digest(cwd/'javascript/index.js'),compiler=load(cwd/'pack-result.json'))
    output([sys.executable,B/'apply.py',root,'--check'])
    target=root/('installers/'+RUNNER_REVISION+'-live-startos-integration')/results.name.rsplit('.',1)[-1]
    need(not target.exists(),'Installer destination already exists; retained')
    # Gate receipts and image manifests accompany every released set.
    receipt=dict(schema=1,milestone='0102',runner_revision=RUNNER_REVISION,source=source,installers=receipts,images=images,ui_images=uis,ui_files=ui_hashes,
        compiled=load(results/'compiled.json'),gates=load(results/'gates.json'),inventories=load(results/'inventories.json'),
        funded_scope='disposable-regtest',mainnet_policy='synthetic-only',startos_host_acceptance=False,
        legacy_wallet_migration=False,retained_0100=cp.digest(results/'retained-0100.json'))
    receipt['workspace']=load(results/'workspace.json')
    if (results/'resume.json').is_file():receipt['resumed_packaging']=load(results/'resume.json')
    save(out/'build-receipt.json',receipt);shutil.copyfile(B/'TEST-STARTOS.md',out/'TEST-STARTOS.md')
    (out/'SHA256SUMS').write_text(''.join(cp.digest(p)+'  '+p.name+'\n' for p in sorted(out.iterdir()) if p.name!='SHA256SUMS'))
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copytree(out,target)
    save(results/'result.json',receipt)
    print('READY: '+RUNNER_REVISION+'; environment-bound policy, compiled live actions, six funded swaps and four bootstrap payments passed; exact engines and packed files verified; three test installers built. StartOS acceptance pending.',flush=True)
    print('INSTALLERS: '+str(target),flush=True)
    for row in receipts.values():print(row['sha256']+'  '+row['package'],flush=True)
    print('LOGS: '+str(results),flush=True)

def diagnostics(results):
    target=results/('diagnostics-'+RUNNER_REVISION+'.zip')
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        for p in results.rglob('*'):
            if not p.is_file() or p.stat().st_size>4*1024*1024:continue
            if p.parent==results and p.suffix in ('.log','.json','.id') or p.name in ('console.log','rpc-errors.jsonl','progress.json','action-result.json','package-result.json','bootstrap-result.json'):
                z.write(p,str(p.relative_to(results)))
    print('DIAGNOSTICS: '+str(target),flush=True)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('previous',type=Path)
    p.add_argument('--resume-pack',type=Path,help='Reuse verified completed 0102/0102a gates and images; repack in a fresh workspace context')
    p.add_argument('root',type=Path,nargs='?',default=Path.home()/'code/cln-blake/privkeyio-migration');a=p.parse_args()
    need(sys.version_info>=(3,12),'Python 3.12 or later required')
    for cmd in ('docker','git','node','start-cli','unsquashfs'):need(shutil.which(cmd),'Required command missing: '+cmd)
    root=a.root.expanduser().absolute();previous=a.previous.expanduser().absolute();os.umask(0o077)
    need(root.is_dir() and not any(p.is_symlink() for p in (root,*root.parents)),'Real migration workspace required')
    runs=root/'build-results';need(not runs.is_symlink(),'Symlinked build-results directory refused');runs.mkdir(exist_ok=True)
    results=Path(tempfile.mkdtemp(prefix='privkeyio-'+RUNNER_REVISION+'-results.',dir=runs));context=results/'build-context';context.mkdir()
    print(RUNNER_REVISION+' starting; logs: '+str(results),flush=True)
    try:
        output([sys.executable,B/'apply.py',root,*(['--check'] if a.resume_pack else [])])
        logged([sys.executable,'-B',B/'test-runner.py'],results/'runner-tests.log')
        logged([sys.executable,'-B',B/'test-pack-resume.py'],results/'resume-tests.log')
        logged([sys.executable,'-B',B/'test-package-checks.py'],results/'package-checks-tests.log')
        packaging_workspace(root,results)
        e=json.loads(output([sys.executable,B/'prior-check.py',root,previous],timeout=300));save(results/'retained-0100.json',e)
        need(cp.digest(root.parent/'bitcoind')==e['retained_0098a']['prior_0096a']['prior_0094a']['compiled_0094']['backend_sha256'],'Fixture backend changed')
        candidate=old_candidate(e)
        tag(e['image'],'preflight-fixture');tag(candidate['images']['node'],'preflight-old-xbt');tag(candidate['images']['ui'],'preflight-xbt-ui')
        for key,i in e['retained_0098a']['images'].items():tag(i,'preflight-'+key)
        source=contexts(root,context,results);node=pull(NODE,results,'compiler');need(node==e['compiled']['node_image'],'Compiler image differs')
        compile_actions(context,results,node)
        for rel,h in source['files'].items():need(cp.digest(context/rel)==h,'Compiler modified tracked input')
        if a.resume_pack:
            saved=a.resume_pack.expanduser().absolute()
            images=module(B/'resume-pack.py','resume0102b').verify(sys.modules[__name__],saved,root,context,results,e,source)
        else:
            images,_=runtime_images(context,results,e);image=harness(context,results,e,images);gates(root,results,image,e)
        pack(root,context,results,e,images,node,source)
    except BaseException:diagnostics(results);raise
if __name__=='__main__':main()
