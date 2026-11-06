"""Validate real 0096a receipts and original provenance without running nodes."""
import json,subprocess,sys
from pathlib import Path
import common as cp
BUNDLE=Path(__file__).resolve().parent

def require(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):require(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),why)
def text(root,name):
    p=cp.ordinary_path(root,name)
    require(p.is_file() and not any(a.is_symlink() for a in (p,*p.parents)) and p.stat().st_size<8*1024*1024,
            'Missing, unsafe or oversized receipt: '+name)
    return p.read_text()
def read(root,name):return json.loads(text(root,name))
def check(payload,bind=False):
    p=subprocess.run([sys.executable,str(BUNDLE/'validate-runtime.py'),*(['--bind'] if bind else [])],
        input=json.dumps(payload,allow_nan=False),text=True,capture_output=True,timeout=60)
    require(p.returncode==0,'0096a evidence/provenance validation failed: '+p.stderr[-1500:])
def validate(e):check(e)
def bind(e,spec,name):check(dict(evidence=e,spec=spec,name=name),bind=True)
def collect(results):
    e=read(results,'runtime-evidence-0096a.json');validate(e)
    for filename,key in [('fixture-source.json','fixture_source'),('unit-result.json','units'),
                         ('compiled-result.json','compiled'),('retained-runtime-0095.json','prior_0094a')]:
        same(read(results,filename),e[key],'Raw receipt differs: '+filename)
    require(text(results,'image.id').strip()==e['image'],'Raw tested image differs')
    require(text(results,'parent-image.id').strip()==e['fixture_source']['parent_image'],'Raw original 0096 image differs')
    for mode in ('retirement','regression'):
        directory=cp.ordinary_path(results,mode);runs=list(directory.glob('privkeyio-0066-*'))
        require(len(runs)==1,'Expected one '+mode+' matrix')
        same(read(runs[0],'progress.json'),dict(stage='complete'),'Incomplete '+mode+' matrix')
        same(read(runs[0],'retirement-result.json' if mode=='retirement' else 'deadline-result.json'),
             e['suites'][mode],'Raw funded result differs: '+mode)
        if mode=='regression':same(read(runs[0],'service-result.json'),e['suites'][mode]['service'],'Raw service regression differs')
    return e
