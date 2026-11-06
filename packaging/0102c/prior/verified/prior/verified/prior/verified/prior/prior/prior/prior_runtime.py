#!/usr/bin/env python3
"""Verify all four complete runtime matrices with separate 0082a/0082c provenance and the reused compiled engines."""
import json
from pathlib import Path
import re

BUNDLE=Path(__file__).resolve().parent
PARENT='sha256:7d7a8401fd07014fb0d4d82a71fb1d135f80fc3559c1f86c9362cee4926cbffa'
COMPILED='69df9aa51c5fa594c7e4854954264ffac46f3924'
CORE_SHA='ab1df9bdd13bcfca1fe1516ba0ee76cd2a2c3a48fa859c49cc9ba3cd4224ea8f'


def require(ok,reason):
    if not ok:raise RuntimeError(reason)


def same(actual,expected,reason):
    require(json.dumps(actual,sort_keys=True,allow_nan=False)==json.dumps(expected,sort_keys=True,allow_nan=False),reason)


def remote_expected():
    cases = []
    for profile in ('btc-cln-v1', 'xbt-privkeyio-v1'):
        for name in ('release', 'fail', 'restart-held'):
            releasing = name != 'fail'
            cases.append(dict(profile=profile,scenario=name,status='complete' if releasing else 'failed',
                authenticated_peer_rpc=True,one_send=True,same_attempt=True,same_incoming_binding=True,
                exact_six_balances=True,terminal_history=True,fee_msat=2000 if releasing else 0,
                lost_registration_reply=True,lost_send_reply=True,lost_resolution_reply=True,
                paused_expired_recovery=name == 'restart-held'))
    return dict(schema=1,fixture='privkeyio-remote-0076',scenarios=cases,regtest_only=True,
        real_rune_enforcement=True,scope_denials=True,lost_mint_recovery=True,aggregate_fee_inclusive_budgets=True,
        restore_barrier=True,core_revocation=True,https_transport=False,cross_chain_controller=False,
        onchain_recovery=False,automatic_payment_retries=False,production_activation_supported=False)



def expected():
    cases = []
    for profile in ('btc-cln-v1', 'xbt-privkeyio-v1'):
        for name in ('release', 'fail', 'restart-held'):
            releasing = name != 'fail'
            cases.append(dict(profile=profile,scenario=name,status='complete' if releasing else 'failed',
                signed_customer_invoice=True,no_core_invoice=True,authenticated_peer_rpc=True,
                one_payment_attempt=True,same_invoice=True,same_incoming_binding=True,
                exact_six_balances=True,terminal_history=True,fee_msat=2000 if releasing else 0,
                lost_signature_reply=True,lost_invoice_reply=True,lost_resolution_reply=True,
                paused_expired_recovery=name == 'restart-held'))
    return dict(schema=1,fixture='privkeyio-customer-0078',scenarios=cases,regtest_only=True,
        old_credentials_not_promoted=True,scoped_readonly_planning=True,independent_signed_publication=True,
        restore_barrier=True,cross_chain_controller=False,https_transport=False,live_market_feed=False,
        onchain_recovery=False,production_activation_supported=False)


def cross_expected():
    cases = []
    for direction in ('forward','reverse'):
        for name in ('release','fail','restart-held'):
            release = name != 'fail'
            cases.append(dict(direction=direction,scenario=name,state='settled' if release else 'failed',
                confirmed_before_enrollment=True,authenticated_peer_rpc=True,signed_customer_invoice=True,
                no_incoming_core_invoice=True,one_outgoing_attempt=True,same_contract=True,same_invoice=True,
                same_incoming_binding=True,exact_twelve_balances=True,terminal_history=True,
                coordinator_fee_msat=2000 if release else 0,payer_fee_msat=2000 if release else 0,
                worker_SIGKILL_after_enrollment=True,worker_SIGKILL_after_invoice=True,worker_SIGKILL_after_send=True,
                worker_SIGKILL_after_resolution=True,both_chains_restarted=name=='restart-held',
                paused_expired_recovery=name=='restart-held'))
    return dict(schema=1,fixture='privkeyio-cross-0080',scenarios=cases,regtest_only=True,cross_chain_worker=True,
        independent_chain_heights=True,synthetic_price_snapshots=True,live_market_feed=False,https_transport=False,
        onchain_recovery=False,automatic_payment_retries=False,production_activation_supported=False)


def https_expected():
    cases = cross_expected()['scenarios']
    for case in cases:
        case.pop('authenticated_peer_rpc')
        case.update(authenticated_https_rpc=True,saved_pairing_unchanged=True)
    return dict(schema=1,fixture='privkeyio-https-0082',scenarios=cases,regtest_only=True,
        cross_chain_worker=True,independent_chain_heights=True,synthetic_price_snapshots=True,
        https_transport=True,native_clnrest=True,real_rune_enforcement=True,wrong_CA_refused=True,
        saved_pairing=True,scoped_https_planning=True,live_market_feed=False,onchain_recovery=False,
        automatic_payment_retries=False,production_activation_supported=False)


SNAPSHOT_KEYS={'phases','build_source','fixture_source','compiled_image','fixture_image','backend_sha256'}


def native_expected():
    return dict(schema=1,fixture='native-clnrest-startup-0082b',
        binaries=json.loads((BUNDLE/'rest-binaries.json').read_text()),native_init=True,verified_https=True,
        missing_rune_refused=True,same_certificates_after_restart=True,clean_EOF_exit=True,daemon_rpc=False,funded=False)


def snapshot(evidence,fixture_id,manifest_name,overlay_name,phases):
    require(set(evidence['phases'])==set(phases),'Runtime phases differ: '+fixture_id)
    expected_results=dict(remote=remote_expected(),customer=expected(),cross=cross_expected(),https=https_expected())
    for phase in phases:
        same(evidence['phases'][phase],dict(progress={'stage':'complete'},result=expected_results[phase]),
             'Incomplete or different '+fixture_id+' '+phase+' receipt')
    manifest=json.loads((BUNDLE/manifest_name).read_text())['lightning']
    files=json.loads((BUNDLE/overlay_name).read_text())
    source=evidence['build_source'];fixture=evidence['fixture_source']
    checkpoints=fixture['checkpoint_commits']
    require(type(checkpoints) is dict and set(checkpoints)=={p['tag'] for p in manifest['checkpoint_chain']}
            and all(type(v) is str and re.fullmatch('[0-9a-f]{40}',v) for v in checkpoints.values()),
            'Fixture checkpoint map differs: '+fixture_id)
    wanted=dict(schema=1,fixture=fixture_id,source_tree=manifest['tree'],compiled_source_tree=COMPILED,
                parent_image=PARENT,files=files,core_unchanged=True,regtest_only=True,installer=False,
                base_tag=manifest['base_tag'],source_checkpoint=checkpoints[manifest['base_tag']],
                checkpoint_commits=checkpoints,rest_plugins=json.loads((BUNDLE/'rest-binaries.json').read_text()))
    same(fixture,wanted,'Fixture source receipt differs: '+fixture_id)
    compiled=json.loads((BUNDLE/'retained-0083-compiled-source.json').read_text())
    compiled['source_checkpoint']=checkpoints['privkeyio-gate-20261011']
    same(source,compiled,'Compiled engine source receipt differs: '+fixture_id)
    require(evidence['compiled_image']==PARENT
            and type(evidence['fixture_image']) is str
            and re.fullmatch(r'sha256:[0-9a-f]{64}',evidence['fixture_image']) is not None
            and evidence['fixture_image']!=PARENT
            and type(evidence['backend_sha256']) is str
            and re.fullmatch('[0-9a-f]{64}',evidence['backend_sha256']) is not None,
            'Runtime image or backend receipt differs: '+fixture_id)


def validate(evidence):
    require(type(evidence) is dict and set(evidence)==SNAPSHOT_KEYS|{'schema','retained','native_startup'},
            'Runtime evidence fields differ')
    require(type(evidence['schema']) is int and evidence['schema']==2,'Runtime evidence schema differs')
    retained=evidence['retained']
    if retained is not None:
        require(type(retained) is dict and set(retained)==SNAPSHOT_KEYS,'Retained evidence fields differ')
        snapshot(retained,'0082a','retained-0083-prior-source-manifest.json','retained-0083-prior-overlay-files.json',('remote','customer','cross'))
        snapshot(evidence,'0082c','retained-0083-source-manifest.json','retained-0083-overlay-files.json',('https',))
        old=retained['fixture_source'];new=evidence['fixture_source']
        for key in ('checkpoint_commits','base_tag','source_checkpoint','compiled_source_tree','parent_image','rest_plugins'):
            same(old[key],new[key],'Retained checkpoint or binary provenance differs: '+key)
        changed={'test_https_engine.py','test_https_fixture.py'}
        require(set(new['files'])==set(old['files'])|{'test_clnrest_startup.py'} and
                all(new['files'][k]==sha for k,sha in old['files'].items() if k not in changed),
                'Retained peer runtime source changed')
        same(retained['backend_sha256'],evidence['backend_sha256'],'Retained backend differs')
        same(retained['build_source'],evidence['build_source'],'Retained compiled source differs')
    else:
        snapshot(evidence,'0082c','retained-0083-source-manifest.json','retained-0083-overlay-files.json',('remote','customer','cross','https'))
    same(evidence['native_startup'],native_expected(),'Native CLNrest startup receipt missing or incomplete')
