"""Validate existing 0092a receipts. No daemon, Docker, or live-node operations."""
import json
from pathlib import Path
import re
import subprocess
import sys

import common as cp
from expected_result import expected, service_expected

BUNDLE=Path(__file__).resolve().parent
BASE_TAG='privkeyio-startos-empty-20261012'
EXPORT_SHA='950bf7b7c090db863b79dde5a941aea300bbee88e2fa3c31114d3fab2761504a'
PARENT='sha256:7d7a8401fd07014fb0d4d82a71fb1d135f80fc3559c1f86c9362cee4926cbffa'
COMPILED='69df9aa51c5fa594c7e4854954264ffac46f3924'
UNITS=dict(tests=120,failures=0,errors=0,skipped=0)


def require(ok,message):
    if not ok:raise RuntimeError(message)


def same(a,b,message):
    require(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),message)


def text(directory,name):
    path=cp.ordinary_path(directory,name)
    require(path.is_file() and path.stat().st_size<8*1024*1024,'Missing or oversized receipt: '+name)
    return path.read_text()


def read(directory,name):return json.loads(text(directory,name))


def historical_summary(e):
    result=subprocess.run([sys.executable,str(BUNDLE/'prior/validate-summary.py')],
        input=json.dumps(e,allow_nan=False),capture_output=True,text=True,timeout=60)
    require(result.returncode==0,'Historical 0091 evidence validation failed')
    return json.loads(result.stdout)


def fixture_expected(checkpoints,controller_checkpoint):
    manifest=read(BUNDLE,'source-manifest.json')
    engine=manifest['lightning'];controller=manifest['swap-controller-startos']
    require(type(checkpoints) is dict and set(checkpoints)=={p['tag'] for p in engine['checkpoint_chain']}
        and all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in checkpoints.values()),
        'Fixture checkpoint ancestry missing')
    require(type(controller_checkpoint) is str and re.fullmatch('[0-9a-f]{40}',controller_checkpoint),
        'Controller checkpoint missing')
    return dict(schema=1,fixture='0092a',source_tree=engine['tree'],source_checkpoint=checkpoints[BASE_TAG],
        base_tag=BASE_TAG,checkpoint_commits=checkpoints,compiled_source_tree=COMPILED,parent_image=PARENT,
        core_unchanged=True,files=read(BUNDLE,'overlay-files.json'),rest_plugins=read(BUNDLE,'rest-binaries.json'),
        regtest_only=True,installer=False,controller_files=read(BUNDLE,'controller-files.json'),
        controller_tree=controller['tree'],controller_checkpoint=controller_checkpoint)


def validate(e):
    fields={'schema','milestone','fixture_source','build_source','parent_image','fixture_image','backend_sha256',
        'units','result','historical_export_sha256','historical_evidence','installer','regtest_only'}
    require(type(e) is dict and set(e)==fields,'0092a evidence fields differ')
    same({k:e[k] for k in ('schema','milestone','parent_image','historical_export_sha256','installer','regtest_only')},
        dict(schema=1,milestone='0092a',parent_image=PARENT,historical_export_sha256=EXPORT_SHA,
            installer=False,regtest_only=True),'0092a evidence scope differs')
    same(e['units'],UNITS,'All 120 unit tests must pass without skips')
    same(e['result'],expected(),'Eight grant setups, six funded cases and populated restore proof required')
    require(type(e['fixture_image']) is str and re.fullmatch('sha256:[0-9a-f]{64}',e['fixture_image'])
        and e['fixture_image']!=PARENT,'Fixture image binding missing')
    fixture=e['fixture_source']
    require(type(fixture) is dict,'Fixture source missing')
    same(fixture,fixture_expected(fixture.get('checkpoint_commits'),fixture.get('controller_checkpoint')),
        '0092a fixture source differs')
    old=historical_summary(e['historical_evidence'])
    same(e['build_source'],old['build_source'],'Reused compiled engine provenance differs')
    same(e['backend_sha256'],old['backend_sha256'],'Fixture backend provenance differs')
    for tag,commit in old['checkpoint_commits'].items():
        require(fixture['checkpoint_commits'][tag]==commit,'Historical engine ancestry differs: '+tag)


def bind(e,spec,name):
    """Bind both current and historical receipts to locally verified Git tags."""
    fixture=e['fixture_source'];checkpoints=spec['checkpoint_commits']
    if name=='lightning':
        same(fixture['checkpoint_commits'],checkpoints,'Tested engine checkpoint ancestry differs')
        require(fixture['source_checkpoint']==spec['base_commit'],'Tested engine base differs')
    if name=='swap-controller-startos':
        require(fixture['controller_checkpoint']==spec['base_commit'],'Tested controller base differs')
    old=e['historical_evidence'];row=old['candidate_build']['repositories'][name]
    tag='privkeyio-backup-recovery-20261012'
    require(row['commit']==checkpoints[tag] and row['tree']==next(p['tree'] for p in spec['checkpoint_chain'] if p['tag']==tag),
        'Historical candidate checkpoint differs: '+name)
    recovery=old['retained_regtest']
    require(recovery['source']['checkpoints'][name]==checkpoints['privkeyio-node-ui-20261012'],
        'Historical recovery checkpoint differs: '+name)
    node=recovery['retained']['original_evidence']
    require(node['source']['checkpoints'][name]==checkpoints['privkeyio-controller-service-20261012'],
        'Historical node/UI checkpoint differs: '+name)
    service=node['retained']['original_evidence']
    if name in ('lightning','swap-controller-startos'):
        prior=read(BUNDLE/'prior','retained-0085-source-manifest.json')[name]
        if name=='lightning':
            same(service['fixture_source']['checkpoint_commits'],
                {p['tag']:checkpoints[p['tag']] for p in prior['checkpoint_chain']},'Historical service engine ancestry differs')
            require(service['fixture_source']['source_checkpoint']==checkpoints[prior['base_tag']],
                'Historical service engine checkpoint differs')
        else:
            require(service['fixture_source']['controller_checkpoint']==checkpoints[prior['base_tag']],
                'Historical service controller checkpoint differs')


def collect(results):
    e=read(results,'runtime-evidence-0092a.json');validate(e)
    for filename,key in [('retained-runtime-0091.json','historical_evidence'),('fixture-source.json','fixture_source'),
                         ('build-source.json','build_source'),('unit-result.json','units')]:
        same(read(results,filename),e[key],'Raw receipt differs: '+filename)
    require(text(results,'parent-image.id').strip()==e['parent_image'],'Parent image receipt differs')
    require(text(results,'image.id').strip()==e['fixture_image'],'Fixture image receipt differs')
    require(text(results,'backend.sha256').split()[0]==e['backend_sha256'],'Backend receipt differs')
    directory=cp.ordinary_path(results,'coordinator')
    require(directory.is_dir(),'Coordinator matrix directory missing')
    runs=list(directory.glob('privkeyio-0066-*'))
    require(len(runs)==1,'Expected exactly one coordinator fixture run')
    relative=str(runs[0].relative_to(results))
    same(read(results,relative+'/progress.json'),dict(stage='complete'),'Coordinator fixture did not complete')
    same(read(results,relative+'/service-result.json'),service_expected(),'Raw service matrix differs')
    same(read(results,relative+'/coordinator-result.json'),e['result'],'Raw populated restore matrix differs')
    return e
