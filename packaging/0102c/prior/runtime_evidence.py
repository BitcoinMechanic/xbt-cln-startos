"""Validate original 0100 raw receipts, compiled inputs and retained provenance."""
import hashlib,importlib.util,json,re,subprocess,sys
from pathlib import Path
import common as cp
BUNDLE=Path(__file__).resolve().parent
VERIFIED=BUNDLE/'verified'
NODE='node:22-bookworm@sha256:8a34c4ab3ea2c5cd194f07e317b2a8f09461d3c8b05c4e34c8ccd56d56024c4d'
REPOS={'controller':'swap-controller-startos','btc':'btc-cln-startos','xbt':'xbt-cln-startos'}
CHECKS=dict(sdk_forms=True,private_commands=True,synthetic_tls_cases=4,full_package_typechecks=3,startos_host=False)
def require(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):
    require(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),why)
def file(root,name):
    p=cp.ordinary_path(root,name)
    require(p.is_file() and not any(a.is_symlink() for a in (p,*p.parents)) and p.stat().st_size<8*1024*1024,
            'Missing, unsafe or oversized receipt/input: '+name)
    return p
def text(root,name):return file(root,name).read_text()
def read(root,name):return json.loads(text(root,name))
def digest(raw):return hashlib.sha256(raw.encode()).hexdigest()
def sha(v):return type(v) is str and re.fullmatch(r'[a-f0-9]{64}',v) is not None
def image(v):return type(v) is str and re.fullmatch(r'sha256:[a-f0-9]{64}',v) is not None
def prior(e,*,spec=None,name=None):
    args=[sys.executable,str(BUNDLE/'validate-prior.py')];data=e
    if spec is not None:args+=['--bind'];data=dict(evidence=e,spec=spec,name=name)
    p=subprocess.run(args,input=json.dumps(data,allow_nan=False),text=True,capture_output=True,timeout=90)
    require(p.returncode==0,'Retained 0098a validation failed: '+p.stderr[-1500:])
def module(name):
    s=importlib.util.spec_from_file_location(name,VERIFIED/(name+'.py'))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m

def harness_files(e):
    c=e['compiled'];source=e['source']['files'];old=e['retained_0098a']
    result={'actions/'+a+'/'+n:h for a,files in c['files'].items() for n,h in files.items()}
    for n in ('test-migration-actions.cjs','migration-action-fixture.cjs','test-migration-process.py'):
        result['actions/'+n]=source['swap-controller-startos/scripts/'+n]
    result['test_startos_actions.py']=source['lightning/tools/swap/test_startos_actions.py']
    result['actions/modules.json']=digest(json.dumps({a:'/opt/actions0100/'+a+'/index.js' for a in REPOS},indent=2)+'\n')
    recipe='FROM swap0100-node:'+c['node_image'][7:]+' AS node\nFROM swap0100-runtime:'+old['fixture_image'][7:]+'\n'
    recipe+='COPY --from=node /usr/local/bin/node /usr/local/bin/node\nCOPY actions/ /opt/actions0100/\n'
    recipe+='COPY test_startos_actions.py /opt/swap0098/test_startos_actions.py\n'
    result['Dockerfile']=digest(recipe)
    return result

def validate(e):
    require(type(e) is dict and set(e)=={'schema','milestone','source','compiled','local_checks','image','actions','suite',
        'retained_0098a','regtest_only','installer','startos_host_acceptance'},'Evidence fields differ')
    same({k:e[k] for k in ('schema','milestone','regtest_only','installer','startos_host_acceptance')},
         dict(schema=1,milestone='0100',regtest_only=True,installer=False,startos_host_acceptance=False),'Evidence scope differs')
    prior(e['retained_0098a'])
    expected=read(VERIFIED,'expected-source.json');commits=e['source']['base_commits']
    require(type(commits) is dict and set(commits)==set(expected['trees']) and all(
        type(c) is str and re.fullmatch(r'[a-f0-9]{40}',c) for c in commits.values()),'Base commit set differs')
    same(e['source'],dict(expected,base_commits=commits),'Exact 0100 source differs')
    old=e['retained_0098a']
    for prefix,key in [('lightning/tools/swap/','files'),('swap-controller-startos/migration/','controller_files')]:
        for rel,h in old['source'][key].items():
            require(expected['files'].get(prefix+rel)==h,'Accepted Python source changed: '+rel)
    same(e['local_checks'],CHECKS,'SDK/process/typecheck receipt differs')
    module('validate-package-result').validate(e['suite'])
    module('validate-actions').validate(e['actions'])
    c=e['compiled']
    require(type(c) is dict and set(c)=={'node_image','node_reference','compiler','files','harness_files'},'Compiler receipt fields differ')
    require(image(c['node_image']) and c['node_reference']==NODE,'Pinned Node image differs')
    require(type(c['compiler']) is dict and set(c['compiler'])==set(REPOS),'Three compiler receipts required')
    tools=read(VERIFIED,'expected-compiler.json');versions=set()
    for asset,wanted in tools.items():
        row=c['compiler'][asset];v=row.get('node')
        require(type(v) is str and re.fullmatch(r'v22\.[0-9]+\.[0-9]+',v),'Node compiler version differs')
        same(row,dict(wanted,node=v),'Locked compiler versions or entry point differ: '+asset);versions.add(v)
    require(len(versions)==1,'Compiler image version differs between packages')
    require(type(c['files']) is dict and set(c['files'])==set(REPOS),'Three compiled handlers required')
    for asset,files in c['files'].items():
        require(type(files) is dict and set(files)=={'index.js'} and sha(files['index.js']),'Compiled SDK handler digest missing: '+asset)
    same(c['harness_files'],harness_files(e),'Harness source or compiled-file inventory differs')
    require(image(e['image']) and e['image'] not in (old['fixture_image'],c['node_image'],*old['images'].values()),
            'Separate 0100 harness image required')
    return e

def bind(e,spec,name):
    require(e['source']['base_commits'][name]==spec['base_commit'] and e['source']['trees'][name]==spec['tree'],
            'Tested source/checkpoint differs: '+name)
    prior(e['retained_0098a'],spec=spec,name=name)

def collect(results):
    e=read(results,'action-evidence-0100.json');validate(e)
    for filename,key in [('source.json','source'),('compiled.json','compiled'),('local-checks.json','local_checks'),
                         ('retained-runtime-0098a.json','retained_0098a')]:
        same(read(results,filename),e[key],'Raw receipt differs: '+filename)
    require(text(results,'image.id').strip()==e['image'],'Raw harness image differs')
    runs=list(cp.ordinary_path(results,'matrix').glob('privkeyio-0066-*'))
    require(len(runs)==1,'Expected one funded action matrix')
    same(read(runs[0],'progress.json'),dict(stage='complete'),'Funded action matrix incomplete')
    same(read(runs[0],'package-result.json'),e['suite'],'Raw six-case matrix differs')
    same(read(runs[0],'action-result.json'),e['actions'],'Raw SDK action coverage differs')
    context=cp.ordinary_path(results,'build-context')
    for name,h in e['source']['files'].items():
        require(cp.digest(file(context,name))==h,'Compiled source input differs: '+name)
    for asset,repo in REPOS.items():
        same(read(context,repo+'/compile-result.json'),e['compiled']['compiler'][asset],'Raw compiler receipt differs: '+asset)
        require(cp.digest(file(context,repo+'/compile.cjs'))==cp.digest(VERIFIED/'compile.cjs'),'Compiler driver differs: '+asset)
        for name,h in e['compiled']['files'][asset].items():
            require(cp.digest(file(context,repo+'/compiled/'+name))==h,'Original compiled handler differs: '+asset)
    for name,h in e['compiled']['harness_files'].items():
        require(cp.digest(file(context,'fixture/'+name))==h,'Funded harness input differs: '+name)
    return e
