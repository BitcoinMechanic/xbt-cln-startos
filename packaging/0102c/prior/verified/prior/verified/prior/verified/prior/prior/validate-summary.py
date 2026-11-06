#!/usr/bin/env python3
"""Validate retained 0092a evidence and bind it to the caller's verified tags."""
import json,sys
import runtime_evidence as runtime
v=json.load(sys.stdin)
if type(v) is dict and set(v)=={'evidence','spec','name'}:
    current=v['spec'];name=v['name'];v=v['evidence']
    spec=runtime.read(runtime.BUNDLE,'source-manifest.json')[name]
    spec['checkpoint_commits']={p['tag']:current['checkpoint_commits'][p['tag']] for p in spec['checkpoint_chain']}
    spec['base_commit']=current['checkpoint_commits'][spec['base_tag']]
    runtime.bind(v,spec,name)
runtime.validate(v)
print(json.dumps(dict(backend_sha256=v['backend_sha256'],build_source=v['build_source'],
    checkpoint_commits=v['fixture_source']['checkpoint_commits'])))
