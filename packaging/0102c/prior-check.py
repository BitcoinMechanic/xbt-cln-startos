#!/usr/bin/env python3
"""Separate interpreter for prior receipt provenance, avoiding import collisions."""
import json,sys
from pathlib import Path
B=Path(__file__).resolve().parent
sys.path.insert(0,str(B/'prior'))
import common as cp
import runtime_evidence as old
root,results=map(Path,sys.argv[1:])
e=old.collect(results)
for name,spec in json.loads((B/'prior/source-manifest.json').read_text()).items():
    points={p['tag']:cp.git(root/name,'rev-parse','refs/tags/'+p['tag']+'^{commit}') for p in spec['checkpoint_chain']}
    spec.update(base_commit=points[spec['base_tag']],checkpoint_commits=points)
    old.bind(e,spec,name)
print(json.dumps(e))
