#!/usr/bin/env python3
"""Isolate historical validators from current helper module names."""
import argparse,json,sys
from pathlib import Path
BUNDLE=Path(__file__).resolve().parent
sys.path.insert(0,str(BUNDLE/'prior'))
import runtime_evidence as old
import common as cp
p=argparse.ArgumentParser();p.add_argument('--results',type=Path);p.add_argument('--root',type=Path);a=p.parse_args()
e=old.collect(a.results) if a.results else json.load(sys.stdin)
old.validate(e)
if a.root:
    manifest=old.read(BUNDLE/'prior','source-manifest.json')
    for name,s in manifest.items():
        repo=a.root/name
        s['base_commit']=cp.git(repo,'rev-parse','refs/tags/'+s['base_tag']+'^{commit}')
        s['checkpoint_commits']={v['tag']:cp.git(repo,'rev-parse','refs/tags/'+v['tag']+'^{commit}') for v in s['checkpoint_chain']}
        old.bind(e,s,name)
print(json.dumps(e))
