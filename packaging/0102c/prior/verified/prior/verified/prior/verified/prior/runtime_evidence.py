"""Validate the passing 0094a receipts without rerunning Docker or funding."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
import common as cp
import runtime_result as matrix
from prepare_build_constants import PARENT,COMPILED,BTC_SHA,PEER_BEFORE,PLUGIN_AFTER

BUNDLE=Path(__file__).resolve().parent
BASE_TAG='privkeyio-coordinator-admin-20261013'
UNITS=dict(tests=149,failures=0,errors=0,skipped=0)
COMPILED_UNITS=dict(tests=147,failures=0,errors=0,skipped=0)
require=matrix.need;same=matrix.same


def text(directory,name):
    p=cp.ordinary_path(directory,name)
    require(p.is_file() and not any(a.is_symlink() for a in (p,*p.parents)) and p.stat().st_size<8*1024*1024,'Missing or oversized receipt: '+name)
    return p.read_text()


def read(directory,name):return json.loads(text(directory,name))

def historical_summary(value,*,spec=None,name=None):
    payload=value if spec is None else dict(evidence=value,spec=spec,name=name)
    result=subprocess.run([sys.executable,str(BUNDLE/'prior/validate-summary.py')],
        input=json.dumps(payload,allow_nan=False),capture_output=True,text=True,timeout=60)
    require(result.returncode==0,'Historical 0093 evidence validation failed')
    return json.loads(result.stdout)


def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True).encode()).hexdigest()

def hexes(value,keys,length):
    require(type(value) is dict and set(value)==set(keys) and all(type(v) is str
        and re.fullmatch('[0-9a-f]{'+str(length)+'}',v) for v in value.values()),'Invalid provenance mapping')


def compiled_source_expected(checkpoints,engine_checkpoints):
    manifest=read(BUNDLE,'base-0094-source-manifest.json')
    hexes(checkpoints,manifest,40)
    hexes(engine_checkpoints,(p['tag'] for p in manifest['lightning']['checkpoint_chain']),40)
    require(checkpoints['lightning']==engine_checkpoints[BASE_TAG],'Compiled engine base differs')
    current=read(BUNDLE,'source-manifest.json')['lightning']['files']
    return dict(schema=1,fixture='0094',base_tag=BASE_TAG,parent_image=PARENT,compiled_parent_tree=COMPILED,
        source_trees={n:s['tree'] for n,s in manifest.items()},checkpoints=checkpoints,engine_checkpoints=engine_checkpoints,
        files=read(BUNDLE,'base-0094-overlay-files.json'),controller_files=read(BUNDLE,'controller-files.json'),
        rest_plugins=read(BUNDLE,'rest-binaries.json'),peer_htlcs_before=PEER_BEFORE,
        peer_htlcs_after=current['lightningd/peer_htlcs.c'],plugin_c_sha256=PLUGIN_AFTER,
        core_patch_sha256=current['tools/swap/onchain-replay.patch'],btc_source_sha256=BTC_SHA,
        recovery_fee_patch=read(BUNDLE,'recovery-fee-patch.json'),gitlinks=read(BUNDLE,'engine-gitlinks.json'),
        versions=dict(btc='v26.06.9-swap0094',xbt='v26.06.9-blake2b.7-swap0094'),regtest_only=True,installer=False)


def overlay_expected(compiled):
    source=compiled['source'];files=read(BUNDLE,'overlay-files.json');old=source['files']
    require(set(files)==set(old) and {n for n in files if files[n]!=old[n]}==
        {'test_deadline_engine.py','test_deadline_fixture.py'},'Fixture repair scope differs')
    return dict(source,fixture='0094a',compiled_image=compiled['images']['patched'],
        compiled_source_sha256=digest(source),source_trees={n:s['tree'] for n,s in read(BUNDLE,'source-manifest.json').items()},files=files)


def weights_valid(weights):
    require(type(weights) is dict and set(weights)=={'baseline','patched'},'Recovery controls missing')
    for kind,rows in weights.items():
        require(type(rows) is list and len(rows)==7,'Seven signed recovery weights required')
        for row,delay in zip(rows,(1,16,17,127,128,4032,32767)):
            require(type(row) is dict and set(row)=={'csv','script','signature','actual','estimated'}
                and all(type(v) is int for v in row.values()),'Invalid recovery weight row')
            require(row['csv']==delay and 37<=row['script']<=39 and 69<=row['signature']<=71
                and row['actual']==164+1+1+row['signature']+1+row['script']
                and (0<row['estimated']<row['actual'] if kind=='baseline' else row['estimated']>=row['actual']),
                'Signed recovery estimate differs')


def validate(e):
    require(type(e) is dict and set(e)=={'schema','milestone','fixture_source','image','compiled_0094','units','suites','regtest_only','installer'},
        '0094a evidence fields differ')
    same({k:e[k] for k in ('schema','milestone','regtest_only','installer')},
        dict(schema=1,milestone='0094a',regtest_only=True,installer=False),'0094a evidence scope differs')
    same(e['units'],UNITS,'All 149 tests required without skips')
    c=e['compiled_0094']
    require(type(c) is dict and set(c)=={'schema','source','images','engines','weights','baseline','baseline_directory','units','historical_evidence','backend_sha256'},
        'Retained compilation fields differ')
    same(c['schema'],1,'Compiled schema differs');same(c['units'],COMPILED_UNITS,'Original unit result differs')
    require(type(c['source']) is dict,'Compiled source missing')
    same(c['source'],compiled_source_expected(c['source'].get('checkpoints'),c['source'].get('engine_checkpoints')),
        'Compiled source provenance differs')
    same(e['fixture_source'],overlay_expected(c),'Tested fixture source differs')
    images=c['images'];require(type(images) is dict and set(images)=={'baseline','patched'},'Compiled image mapping differs')
    ids=[PARENT,e['image'],*images.values()]
    require(all(type(v) is str and re.fullmatch('sha256:[0-9a-f]{64}',v) for v in ids) and len(set(ids))==4,
        'Distinct original, baseline, compiled and fixture images required')
    hexes(c['engines'],('/opt/btc/bin/lightningd','/opt/xbt/bin/lightningd'),64)
    weights_valid(c['weights'])
    require(type(c['baseline_directory']) is str and re.fullmatch('privkeyio-0066-[A-Za-z0-9_-]{1,100}',c['baseline_directory']),
        'Baseline directory invalid')
    prior=historical_summary(c['historical_evidence'])
    same(c['backend_sha256'],prior['backend_sha256'],'Backend provenance differs')
    for tag,commit in prior['checkpoint_commits'].items():
        require(c['source']['engine_checkpoints'][tag]==commit,'Historical engine checkpoint differs: '+tag)
    previous=c['historical_evidence']['result']
    matrix.result(c['baseline'],'baseline',previous)
    require(type(e['suites']) is dict and set(e['suites'])=={'patched','regression'},'Fresh funded matrices missing')
    for mode in ('patched','regression'):matrix.result(e['suites'][mode],mode,previous)


def bind(e,spec,name):
    source=e['fixture_source'];c=e['compiled_0094']
    require(source['checkpoints'][name]==spec['base_commit'],'Tested checkpoint differs: '+name)
    require(source['source_trees'][name]==spec['tree'],'Tested source tree differs: '+name)
    if name=='lightning':same(source['engine_checkpoints'],spec['checkpoint_commits'],'Tested engine ancestry differs')
    historical_summary(c['historical_evidence'],spec=spec,name=name)


def engine_hashes(raw):
    values={}
    for row in raw.splitlines():
        h,path=row.split();require(path not in values,'Duplicate engine hash');values[path]=h
    hexes(values,('/opt/btc/bin/lightningd','/opt/xbt/bin/lightningd'),64);return values


def weights_text(kind,rows):
    suffix='BASELINE: all seven recovery witnesses underestimated' if kind=='baseline' else 'PATCHED: all seven recovery witnesses covered'
    return ''.join('csv={csv} script={script} signature={signature} actual={actual} estimated={estimated}\n'.format(**r) for r in rows)+suffix+'\n'


def collect(results):
    e=read(results,'runtime-evidence-0094a.json');validate(e);c=e['compiled_0094']
    same(read(results,'fixture-source.json'),e['fixture_source'],'Raw overlay source differs')
    same(read(results,'unit-result.json'),e['units'],'Raw unit result differs')
    require(text(results,'image.id').strip()==e['image'],'Raw overlay image differs')
    require(text(results,'compiled-image.id').strip()==c['images']['patched'],'Raw compiled image differs')
    same(engine_hashes(text(results,'engines.sha256')),c['engines'],'Raw current engine hashes differ')
    same(read(results,'reused-build.json'),dict(compiled_image=c['images']['patched'],engines=c['engines'],
        retained_baseline=c['baseline'],fixture_only_files=['test_deadline_engine.py','test_deadline_fixture.py']),
        'Raw reuse receipt differs')
    prior=cp.ordinary_path(results,'compiled-0094')
    for filename,key in [('fixture-source.json','source'),('unit-result.json','units'),('retained-runtime-0093.json','historical_evidence')]:
        same(read(prior,filename),c[key],'Retained raw receipt differs: '+filename)
    require(text(prior,'parent-image.id').strip()==PARENT,'Original parent image differs')
    require(text(prior,'image.id').strip()==c['images']['patched'] and text(prior,'baseline-image.id').strip()==c['images']['baseline'],
        'Retained raw image differs')
    same(engine_hashes(text(prior,'engines.sha256')),c['engines'],'Retained raw engine hashes differ')
    require(text(prior,'backend.sha256').split()[0]==c['backend_sha256'],'Retained backend hash differs')
    same(read(prior,'build-source.json'),c['historical_evidence']['build_source'],'Original engine build receipt differs')
    for kind in ('baseline','patched'):
        require(text(prior,kind+'-recovery-weight.txt')==weights_text(kind,c['weights'][kind]),'Raw signed weight control differs')
    runs=list((prior/'baseline').glob('privkeyio-0066-*'))
    require(len(runs)==1 and runs[0].name==c['baseline_directory'],'Retained baseline directory differs')
    same(read(runs[0],'progress.json'),dict(stage='complete'),'Retained baseline incomplete')
    same(read(runs[0],'deadline-result.json'),c['baseline'],'Raw original-binary controls differ')
    for mode in ('patched','regression'):
        directory=cp.ordinary_path(results,mode);runs=list(directory.glob('privkeyio-0066-*'))
        require(len(runs)==1,'Expected one '+mode+' matrix')
        same(read(runs[0],'progress.json'),dict(stage='complete'),'Incomplete '+mode+' matrix')
        same(read(runs[0],'deadline-result.json'),e['suites'][mode],'Raw funded result differs: '+mode)
        if mode=='regression':same(read(runs[0],'service-result.json'),e['suites'][mode]['service'],'Raw service regression differs')
    return e
