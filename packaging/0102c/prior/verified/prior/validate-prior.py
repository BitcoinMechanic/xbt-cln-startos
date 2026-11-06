#!/usr/bin/env python3
"""Isolate unchanged historical validators from the current checkpoint module."""
import json,sys
from pathlib import Path
B=Path(__file__).resolve().parent
sys.path.insert(0,str(B/'verified/prior'))
import runtime_evidence as old
request=json.load(sys.stdin)
if len(sys.argv)==1:old.validate(request)
else:
    assert sys.argv[1:]==['--bind']
    e,spec,name=request['evidence'],request['spec'],request['name']
    points=spec['checkpoint_commits']
    previous=json.loads((B/'verified/prior/source-manifest.json').read_text())[name]
    previous['base_commit']=points[previous['base_tag']]
    previous['checkpoint_commits']={p['tag']:points[p['tag']] for p in previous['checkpoint_chain']}
    old.bind(e,previous,name)
print('{}')
