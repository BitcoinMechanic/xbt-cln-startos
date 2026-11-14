#!/usr/bin/env python3
"""Six service cases plus 24 retained cases, preserving separate provenance."""
import json
from pathlib import Path
import re
import prior_runtime as prior

BUNDLE=Path(__file__).resolve().parent
require=prior.require
same=prior.same


def expected():
    cases=[]
    for d in ('forward','reverse'):
        for n in ('release','fail','restart-held'):
            cases.append(dict(direction=d,scenario=n,state='failed' if n=='fail' else 'settled',automatic_worker=True,
                confirmed_before_enrollment=True,signed_customer_invoice=True,one_outgoing_attempt=True,
                original_contract_invoice_HTLC_attempt=True,exact_twelve_balances=True,
                SIGKILL_after_enrollment_invoice_send_resolution=True,service_pause_recovery=True,
                saved_markup_unchanged=True,history_count=('release','fail','restart-held').index(n)+1,
                both_chains_restarted=n=='restart-held',paused_expired_recovery=n=='restart-held',
                renewed_grants_preserve_history=n=='restart-held'))
    return dict(schema=1,fixture='privkeyio-service-0084',scenarios=cases,regtest_only=True,native_https=True,
        cached_offline_history=True,synthetic_price_snapshots=True,live_market_feed=False,
        startos_actions_registered=False,installer=False)


def validate(evidence):
    require(type(evidence) is dict and set(evidence)=={
        'schema','service','build_source','fixture_source','compiled_image','fixture_image','backend_sha256','retained'},
        'Service evidence fields differ')
    require(type(evidence['schema']) is int and evidence['schema']==3,'Service evidence schema differs')
    same(evidence['service'],dict(progress=dict(stage='complete'),result=expected()),'Incomplete service matrix')
    retained=evidence['retained'];prior.validate(retained)
    spec=json.loads((BUNDLE/'retained-0085-source-manifest.json').read_text())
    e,c=spec['lightning'],spec['swap-controller-startos'];fixture=evidence['fixture_source']
    checkpoints=fixture['checkpoint_commits']
    require(type(checkpoints) is dict and set(checkpoints)=={p['tag'] for p in e['checkpoint_chain']}
            and all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in checkpoints.values()),
            'Service checkpoint map differs')
    controller=fixture['controller_checkpoint']
    require(type(controller) is str and re.fullmatch('[0-9a-f]{40}',controller) is not None,
            'Controller checkpoint missing')
    files=json.loads((BUNDLE/'overlay-files.json').read_text())
    wanted=dict(schema=1,fixture='0084',source_tree=e['tree'],source_checkpoint=checkpoints[e['base_tag']],
        base_tag=e['base_tag'],checkpoint_commits=checkpoints,compiled_source_tree=prior.COMPILED,
        parent_image=prior.PARENT,core_unchanged=True,files=files,
        rest_plugins=json.loads((BUNDLE/'rest-binaries.json').read_text()),regtest_only=True,installer=False,
        controller_files=json.loads((BUNDLE/'controller-files.json').read_text()),controller_tree=c['tree'],
        controller_checkpoint=controller)
    same(fixture,wanted,'Service source receipt differs')
    old=retained['fixture_source']
    require(old['source_tree']==e['before_tree'],'Retained runtime differs from service base tree')
    require(all(checkpoints.get(tag)==commit for tag,commit in old['checkpoint_commits'].items()),
            'Retained checkpoint ancestry differs')
    require(all(files.get(name)==sha for name,sha in old['files'].items()),'Retained runtime modules changed')
    same(evidence['build_source'],retained['build_source'],'Compiled source changed')
    require(evidence['build_source']['source_checkpoint']==checkpoints['privkeyio-gate-20261011'],
            'Compiled source checkpoint changed')
    require(evidence['compiled_image']==prior.PARENT,'Compiled image changed')
    image=evidence['fixture_image']
    require(type(image) is str and re.fullmatch('sha256:[0-9a-f]{64}',image) is not None
            and image!=prior.PARENT,'Service image receipt invalid')
    same(evidence['backend_sha256'],retained['backend_sha256'],'Backend changed')
