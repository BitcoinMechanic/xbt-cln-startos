#!/usr/bin/env python3
"""Isolate current and historical validator imports; no Docker or network."""
import json,sys
from pathlib import Path
B=Path(__file__).resolve().parent
request=json.load(sys.stdin)
if len(sys.argv)==1:
    sys.path.insert(0,str(B/'verified'))
    import runtime_result as r
    r.validate(request)
else:
    assert sys.argv[1:] == ['--bind']
    e,spec,name=request['evidence'],request['spec'],request['name']
    s=e['fixture_source'];points=spec['checkpoint_commits']
    if s['base_commits'][name]!=spec['base_commit'] or s['source_trees'][name]!=spec['tree']:
        raise RuntimeError('Tested checkpoint/source differs: '+name)
    sys.path.insert(0,str(B/'verified/prior'))
    import runtime_evidence as old
    prior=json.loads((B/'verified/prior/source-manifest.json').read_text())[name]
    prior['base_commit']=points[prior['base_tag']]
    prior['checkpoint_commits']={p['tag']:points[p['tag']] for p in prior['checkpoint_chain']}
    old.bind(e['prior_0094a'],prior,name)
print('{}')
