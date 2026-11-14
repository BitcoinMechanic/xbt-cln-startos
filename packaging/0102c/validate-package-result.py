"""Strict current receipt shape, independent of retained historical matrices."""
import json
from pathlib import Path

def need(v,reason):
    if not v:raise RuntimeError(reason)
def same(a,b,reason):need(json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True),reason)

def validate(r):
    expected=dict(schema=1,fixture='privkeyio-packaged-runtime-0098',regtest_only=True,installer=False,
        startos_acceptance=False,synthetic_market_reader=True,fixture_code_in_runtime=False,
        engine_recompiled=False,backup_restore=False,closed_channels=0)
    need(set(r)==set(expected)|{'grants','cases'},'Result fields differ')
    same({k:r[k] for k in expected},expected,'Result scope differs')
    need(len(r['grants'])==4,'Expected four original grants')
    for row,(profile,kind) in zip(r['grants'],[(p,k) for p in ('btc-cln-v1','xbt-privkeyio-v1') for k in ('outgoing','incoming')]):
        same(row,dict(profile=profile,kind=kind,channel_count=1,review_without_authority=True,
            fresh_process_confirmation=True,lost_reply_same_grant=True),'Grant receipt differs')
    need(len(r['cases'])==6,'Expected six funded cases')
    generation='a'
    for row,(d,n) in zip(r['cases'],[(d,n) for d in ('forward','reverse') for n in ('restart-held','fail','update-held')]):
        after=('b' if generation=='a' else 'a') if n=='update-held' else generation
        same(row,dict(direction=d,scenario=n,state='failed' if n=='fail' else 'settled',generation_before=generation,generation_after=after,
            original_identity_channels_credentials=True,original_contract_invoice_HTLC_attempt=True,one_outgoing_attempt=True,
            exact_twelve_balances=True,deadline_armed=True,closed_channels=0,history_count=('restart-held','fail','update-held').index(n)+1,
            controller_SIGKILL=n!='fail',node_restart=n!='fail',package_replaced=n=='update-held'),'Funded case differs')
        generation=after
