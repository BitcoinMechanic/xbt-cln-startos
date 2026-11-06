#!/usr/bin/env python3
"""Validate historical receipts in their own import namespace."""
import json,sys
import runtime_evidence as runtime
value=json.load(sys.stdin);runtime.validate(value)
node=value['retained_regtest']['retained']['original_evidence']
service=node['retained']['original_evidence']
print(json.dumps(dict(backend_sha256=node['backend_sha256'],build_source=service['build_source'],
    checkpoint_commits=service['fixture_source']['checkpoint_commits'],
    candidate_repositories=value['candidate_build']['repositories'])))
