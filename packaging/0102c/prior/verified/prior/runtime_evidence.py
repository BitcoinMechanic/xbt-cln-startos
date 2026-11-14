"""Read-only validation of 0098a raw receipts, runtimes and retained provenance."""
import importlib.util,json,re,subprocess,sys
from pathlib import Path
import common as cp
BUNDLE=Path(__file__).resolve().parent
VERIFIED=BUNDLE/'verified'

def require(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):
    require(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),why)
def text(root,name):
    p=cp.ordinary_path(root,name)
    require(p.is_file() and not any(a.is_symlink() for a in (p,*p.parents)) and p.stat().st_size<8*1024*1024,
            'Missing, unsafe or oversized receipt: '+name)
    return p.read_text()
def read(root,name):return json.loads(text(root,name))
def prior(e,*,spec=None,name=None):
    args=[sys.executable,str(BUNDLE/'validate-prior.py')]
    data=e
    if spec is not None:args+=['--bind'];data=dict(evidence=e,spec=spec,name=name)
    p=subprocess.run(args,input=json.dumps(data,allow_nan=False),text=True,capture_output=True,timeout=60)
    require(p.returncode==0,'Retained 0096a provenance validation failed: '+p.stderr[-1500:])
def image_id(v):return type(v) is str and re.fullmatch(r'sha256:[a-f0-9]{64}',v) is not None
def sha(v):return type(v) is str and re.fullmatch(r'[a-f0-9]{64}',v) is not None

def native(v):
    require(type(v) is dict and 3<=len(v)<=10000,'Native inventory missing')
    for name,row in v.items():
        path=Path(name)
        require(type(name) is str and name and not path.is_absolute() and '..' not in path.parts,
                'Native inventory path differs')
        require(type(row) is dict,'Native inventory record differs')
        if set(row)=={'link'}:
            require(type(row['link']) is str and 0<len(row['link'])<=4096,'Invalid native symlink')
        else:
            require(set(row)=={'sha256','executable'} and sha(row['sha256']) and type(row['executable']) is bool,
                    'Invalid native file digest/mode')

def validate(e):
    require(type(e) is dict and set(e)=={'schema','milestone','source','images','fixture_image','runtime_manifests',
        'inventories','extracted','units','suite','prior_0096a','regtest_only','installer'},'Evidence fields differ')
    same({k:e[k] for k in ('schema','milestone','regtest_only','installer')},
         dict(schema=1,milestone='0098a',regtest_only=True,installer=False),'Evidence scope differs')
    prior(e['prior_0096a'])
    expected=read(VERIFIED,'expected-source.json');commits=e['source']['base_commits']
    require(type(commits) is dict and set(commits)==set(expected['trees']) and all(
        type(c) is str and re.fullmatch(r'[a-f0-9]{40}',c) for c in commits.values()),'Base commits differ')
    same(e['source'],dict(expected,base_commits=commits),'Exact tested source differs')
    same(e['units'],dict(tests=177,failures=0,errors=0,skipped=0),'All 177 units required without skips')
    spec=importlib.util.spec_from_file_location('packaged_result',VERIFIED/'validate-result.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);module.validate(e['suite'])
    manifests=read(VERIFIED,'expected-runtime-manifests.json')
    runtimes=read(VERIFIED,'expected-runtime-inventories.json')
    same(e['runtime_manifests'],manifests,'Runtime manifest source differs')
    require(type(e['images']) is dict and set(e['images'])==set(manifests) and
            all(image_id(i) for i in e['images'].values()),'Six immutable runtime images required')
    old=e['prior_0096a']
    require(image_id(e['fixture_image']) and e['fixture_image'] not in [old['image'],*e['images'].values()],
            'Separate immutable harness image required')
    require(set(e['inventories'])==set(manifests) and set(e['extracted'])=={'a','b'},'Runtime inventories missing')
    for asset in ('btc','xbt','controller'):
        require(e['images'][asset+'-a']!=e['images'][asset+'-b'],'Distinct replacement images required')
        for generation in ('a','b'):
            key=asset+'-'+generation;observed=e['inventories'][key]
            fields={'manifest','runtime'} if asset=='controller' else {'manifest','runtime','native','version','shared_libraries_available'}
            require(type(observed) is dict and set(observed)==fields,'Image inventory fields differ')
            same(observed['manifest'],manifests[key],'Image manifest differs')
            same(observed['runtime'],runtimes[key],'Packaged files or modes differ')
            if asset!='controller':
                native(observed['native'])
                require(observed['shared_libraries_available'] is True,'Native library check missing')
                same(observed['version'],old['compiled']['versions'][asset],'Retained engine version differs')
                same(observed['native']['bin/lightningd'],dict(sha256=old['compiled']['engines']['/opt/'+asset+'/bin/lightningd'],executable=True),'Retained engine bytes differ')
                same(observed['native']['libexec/c-lightning/plugins/clnrest'],
                     dict(sha256=old['fixture_source']['rest_plugins'][asset],executable=True),'Retained native REST bytes differ')
                require(observed['native']['bin/lightning-cli']['executable'] is True,'Packaged CLI missing')
        if asset!='controller':same(e['inventories'][asset+'-a']['native'],e['inventories'][asset+'-b']['native'],'Replacement native bytes differ')
    for generation in ('a','b'):
        expected_extraction={a:e['inventories'][a+'-'+generation]['native'] for a in ('btc','xbt')}
        expected_extraction.update(node=runtimes['btc-'+generation],controller=runtimes['controller-'+generation])
        same(e['extracted'][generation],expected_extraction,'Harness extraction differs')
    return e

def bind(e,spec,name):
    require(e['source']['base_commits'][name]==spec['base_commit'] and e['source']['trees'][name]==spec['tree'],
            'Tested source/checkpoint differs: '+name)
    prior(e['prior_0096a'],spec=spec,name=name)

def collect(results):
    e=read(results,'runtime-evidence-0098a.json');validate(e)
    for filename,key in [('source.json','source'),('images.json','images'),('runtime-manifests.json','runtime_manifests'),
            ('runtime-inventories.json','inventories'),('extracted-inventories.json','extracted'),
            ('unit-result.json','units'),('retained-runtime-0096a.json','prior_0096a')]:
        same(read(results,filename),e[key],'Raw receipt differs: '+filename)
    require(text(results,'image.id').strip()==e['fixture_image'],'Raw harness image differs')
    require(text(results,'parent-image.id').strip()==e['prior_0096a']['image'],'Raw retained parent image differs')
    for key,image in e['images'].items():
        require(text(results,key+'.image.id').strip()==image,'Raw runtime image differs: '+key)
    old=e['prior_0096a'];s=old['fixture_source']
    expected=dict(source=s,files=s['files'],controller=s['controller_files'],engines=old['compiled']['engines'],
        rest=s['rest_plugins'],versions=old['compiled']['versions'],
        native={a:e['inventories'][a+'-a']['native'] for a in ('btc','xbt')})
    same(read(results,'parent-inventory.json'),expected,'Original parent inventory differs')
    runs=list(cp.ordinary_path(results,'matrix').glob('privkeyio-0066-*'))
    require(len(runs)==1,'Expected one packaged matrix')
    same(read(runs[0],'progress.json'),dict(stage='complete'),'Packaged matrix incomplete')
    same(read(runs[0],'package-result.json'),e['suite'],'Raw funded matrix differs')
    return e
