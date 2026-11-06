"""Strict 0096a receipts, preserving historical provenance separately."""
import hashlib,json,re,subprocess,sys
from pathlib import Path
import common as cp
BUNDLE=Path(__file__).resolve().parent
UNITS=dict(tests=169,failures=0,errors=0,skipped=0)

def need(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):need(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),why)
def read(directory,name):
    p=cp.ordinary_path(directory,name)
    need(p.is_file() and not any(v.is_symlink() for v in (p,*p.parents)) and p.stat().st_size<8*1024*1024,'Unsafe/missing receipt: '+name)
    return json.loads(p.read_text())
def digest(v):return hashlib.sha256(json.dumps(v,sort_keys=True).encode()).hexdigest()
def prior(e=None,*,results=None,root=None):
    args=[sys.executable,str(BUNDLE/'prior-evidence.py')]
    if results is not None:args+=['--results',str(results)]
    if root is not None:args+=['--root',str(root)]
    p=subprocess.run(args,input=None if e is None else json.dumps(e),capture_output=True,text=True,timeout=60)
    need(p.returncode==0,'Prior 0094a source/evidence validation failed: '+p.stderr[-1000:])
    return json.loads(p.stdout)
def checkpoints(root):
    return {n:cp.git(root/n,'rev-parse','refs/tags/privkeyio-deadline-20261013^{commit}') for n in read(BUNDLE,'source-manifest.json')}
def original_source(e,commits):
    need(set(commits)==set(read(BUNDLE,'original-0096-source-manifest.json')) and all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in commits.values()),'Invalid base commits')
    return dict(schema=1,fixture='0096',base_tag='privkeyio-deadline-20261013',base_commits=commits,
        source_trees={n:s['tree'] for n,s in read(BUNDLE,'original-0096-source-manifest.json').items()},
        files=read(BUNDLE,'original-0096-overlay-files.json'),controller_files=read(BUNDLE,'controller-files.json'),
        rest_plugins=e['fixture_source']['rest_plugins'],compiled_engines=e['compiled_0094']['engines'],
        parent_image=e['image'],compiled_image=e['compiled_0094']['images']['patched'],
        retained_evidence_sha256=digest(e),regtest_only=True,installer=False)
def btc_sources():
    return {Path(n).name:h['after'] for n,h in read(BUNDLE,'source-manifest.json')['lightning']['files'].items()
            if n in ('tools/swap/btc-recovery-fees.patch','tools/swap/test_btc_recovery_weight.c')}
def image_id(value):return type(value) is str and re.fullmatch('sha256:[0-9a-f]{64}',value)
def source(e,commits,parent):
    s=original_source(e,commits)
    need(image_id(parent) and parent not in (e['image'],e['compiled_0094']['images']['patched']), 'Original 0096 image required')
    s.update(fixture='0096a',source_trees={n:v['tree'] for n,v in read(BUNDLE,'source-manifest.json').items()},
        files=read(BUNDLE,'overlay-files.json'),parent_image=parent,
        btc_recovery=dict(source_zip_sha256='ac37b1b6c41b6c60cf06dd8cd7500f1fab04411cf2f3bc126838d8cafab4538d',files=btc_sources()),
        versions=dict(btc='v26.06.9-swap0096a',xbt='v26.06.9-blake2b.7-swap0094'))
    s['original_engines']=s.pop('compiled_engines')
    return s

def compiled(v,e):
    need(type(v) is dict and set(v)=={'engines','btc_controls','btc_vectors','versions'}, 'BTC build evidence fields differ')
    engines=v['engines'];old=e['compiled_0094']['engines'];need(set(engines)==set(old),'Engine paths differ')
    need(all(type(h) is str and re.fullmatch('[0-9a-f]{64}',h) for h in engines.values()), 'Invalid engine hashes')
    need(engines['/opt/xbt/bin/lightningd']==old['/opt/xbt/bin/lightningd'] and engines['/opt/btc/bin/lightningd']!=old['/opt/btc/bin/lightningd'],
         'BTC must be rebuilt and XBT retained')
    same(v['versions'],dict(btc='v26.06.9-swap0096a',xbt='v26.06.9-blake2b.7-swap0094'),'Engine versions differ')
    need(set(v['btc_controls'])==set(v['btc_vectors'])=={'baseline','patched'},'BTC fee controls missing')
    for kind in ('baseline','patched'):
        rows=v['btc_controls'][kind].splitlines();need(len(rows)==8,'Seven signed BTC witness controls required')
        suffix='BASELINE: all seven recovery witnesses underestimated' if kind=='baseline' else 'PATCHED: all seven recovery witnesses covered'
        need(rows[-1]==suffix,'Signed BTC control outcome differs')
        for row,csv,size in zip(rows[:-1],(1,16,17,127,128,4032,32767),(37,37,38,38,39,39,39)):
            m=re.fullmatch(r'csv=(\d+) script=(\d+) signature=(\d+) actual=(\d+) estimated=(\d+)',row)
            need(m is not None,'Malformed BTC weight control')
            c,l,sig,actual,est=map(int,m.groups())
            need(c==csv and l==size and 65<=sig<=71 and actual==164+1+1+sig+1+l
                 and est==(239 if kind=='baseline' else 277)
                 and ((est<actual) if kind=='baseline' else (est>=actual)), 'Signed BTC witness weight incorrect')
        baseline=kind=='baseline'
        same(v['btc_vectors'][kind],dict(actual_weight=891,vsize=223,estimated_weight=855 if baseline else 893,
            fee_at_253_perkw=216 if baseline else 225,baseline=baseline,serialized_witnesses=True),
            'Posted transaction fee regression differs')
    return v
def deadline(value,mode,e):
    # Run the exact prior matrix schema in a separate import namespace.
    code="import json,sys;sys.path.insert(0,sys.argv[1]);import runtime_result as r;v=json.load(sys.stdin);r.result(v['value'],v['mode'],v['previous'])"
    p=subprocess.run([sys.executable,'-c',code,str(BUNDLE/'prior')],
        input=json.dumps(dict(value=value,mode=mode,previous=e['compiled_0094']['historical_evidence']['result'])),
        text=True,capture_output=True,timeout=30)
    need(p.returncode==0,'Current deadline/service regression incomplete')
def retirement(value,e):
    header=dict(schema=1,fixture='privkeyio-retirement-0096',regtest_only=True,installer=False)
    need(type(value) is dict and set(value)==set(header)|{'deadline_cases','retirement_cases'},'Retirement result fields differ')
    same({k:value[k] for k in header},header,'Retirement scope differs')
    deadline(dict(schema=1,fixture='privkeyio-deadline-0094a',mode='patched',regtest_only=True,installer=False,
        cases=value['deadline_cases']),'patched',e)
    cases=value['retirement_cases'];need(type(cases) is list and len(cases)==6,'Six retirements required')
    for row,(d,n) in zip(cases,[(d,n) for d in ('forward','reverse') for n in ('release','timeout','restart-held')]):
        expected=dict(direction=d,scenario=n,closed_history_verified=True,original_htlc_pruned_by_core=True,
            original_binding_preserved=True,depth_100=True,separate_local_and_controller_review=True,
            wrong_confirmation_refused=True,old_rune_retirement_refused=True,fresh_process_lost_reply=True,
            controller_retirement_SIGKILL=True,post_renewal_restart=True,original_attempt_preserved=True,
            one_close=True,one_send=True,premature_renewal_refused=True,new_funding_grant_renewed=True,
            budget_not_refunded=True,default_fee_recovered_input=True,backend_relay_verified=True,terminal_state='onchain_failed' if n=='timeout' else 'onchain_settled',
            phase='timeout_verified' if n=='timeout' else 'claim_and_sweep_verified')
        same(row,expected,'Retirement case incomplete')
def validate(v,root=None):
    need(type(v) is dict and set(v)=={'schema','milestone','fixture_source','image','prior_0094a','units','suites','compiled','regtest_only','installer'},'Evidence fields differ')
    same({k:v[k] for k in ('schema','milestone','regtest_only','installer')},dict(schema=1,milestone='0096a',regtest_only=True,installer=False),'Evidence scope differs')
    e=prior(v['prior_0094a'],root=root);same(v['units'],UNITS,'All 169 units required without skips')
    commits=checkpoints(root) if root else v['fixture_source']['base_commits']
    same(v['fixture_source'],source(e,commits,v['fixture_source']['parent_image']),'Fixture source differs')
    compiled(v['compiled'],e)
    need(type(v['image']) is str and re.fullmatch('sha256:[0-9a-f]{64}',v['image'])
         and v['image'] not in (e['image'],e['compiled_0094']['images']['patched'],v['fixture_source']['parent_image']),'New immutable fixture image required')
    need(type(v['suites']) is dict and set(v['suites'])=={'retirement','regression'},'Funded suites missing')
    retirement(v['suites']['retirement'],e);deadline(v['suites']['regression'],'regression',e)
    return v
