#!/usr/bin/env python3
"""Packaged XBT node/UI result and retained swap matrices, with separate provenance."""
import json
from pathlib import Path
import re
import service_runtime as service

BUNDLE=Path(__file__).resolve().parent
require=service.require
same=service.same
PRIOR_EXPORT='43312543408e4e8238e6acef6cf75d8f649b6d7879dae13bd98df9a615615617'


def expected():
    return dict(schema=1,fixture='packaged-xbt-ui-0086',regtest_only=True,installer=False,
        native_rest_and_grpc=True,ui_auth_and_csrf=True,foreign_invoice_refused=True,
        ui_address_and_channel=True,ui_payments=4,original_funding_and_signing=True,
        node_and_ui_restart=True,full_backup_recovery=False,live_migration=False)


def validate(evidence):
    require(type(evidence) is dict and set(evidence)=={'schema','fixture','source','images',
        'backend_sha256','result','retained','regtest_only','installer'},'Node/UI evidence fields differ')
    same({k:evidence[k] for k in ('schema','fixture','regtest_only','installer')},
         dict(schema=1,fixture='0086',regtest_only=True,installer=False),'Node/UI scope differs')
    same(evidence['result'],expected(),'Incomplete or inflated node/UI result')
    manifest=json.loads((BUNDLE/'retained-0087-source-manifest.json').read_text())
    source=evidence['source'];require(type(source) is dict,'Source receipt missing')
    checkpoints=source.get('checkpoints')
    require(type(checkpoints) is dict and set(checkpoints)==set(manifest) and
        all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in checkpoints.values()),'Checkpoint map differs')
    wanted=json.loads((BUNDLE/'retained-0087-build-source.json').read_text())
    same(source,dict(wanted,checkpoints=checkpoints),'Tested build source differs')
    require(checkpoints['lightning']==wanted['source_lock']['engine']['commit'],'Pinned engine commit differs')
    images=evidence['images']
    require(type(images) is dict and set(images)=={'node','ui','btc','fixture'} and
        all(type(v) is str and re.fullmatch('sha256:[0-9a-f]{64}',v) for v in images.values()),'Image receipt differs')
    require(images['btc']==service.prior.PARENT and len(set(images.values()))==4,'Build images are not distinct or BTC control differs')
    sha=evidence['backend_sha256']
    require(type(sha) is str and re.fullmatch('[0-9a-f]{64}',sha),'Invalid backend hash')
    retained=evidence['retained']
    require(type(retained) is dict and set(retained)=={'schema','export_sha256','original_evidence','retained_cases'},
        'Retained export fields differ')
    same({k:retained[k] for k in ('schema','export_sha256','retained_cases')},
        dict(schema=1,export_sha256=PRIOR_EXPORT,retained_cases=30),'Retained export identity differs')
    service.validate(retained['original_evidence'])
    require(retained['original_evidence']['backend_sha256']==sha,'Backend changed from retained fixtures')
    require(wanted['source_lock']['engine']['tree']==manifest['lightning']['tree'] and
        retained['original_evidence']['fixture_source']['source_tree']==manifest['lightning']['tree'],
        'Retained engine source tree changed')
    require(retained['original_evidence']['fixture_source']['controller_tree']==manifest['swap-controller-startos']['tree'],
        'Retained controller source tree changed')
