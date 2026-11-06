"""Strict 0094 receipt schemas; no synthetic result is funded acceptance."""
import json,re
from pathlib import Path

def need(ok,why):
    if not ok:raise RuntimeError(why)
def same(a,b,why):need(json.dumps(a,sort_keys=True,allow_nan=False)==json.dumps(b,sort_keys=True,allow_nan=False),why)
def read(root,name):
    path=root/name
    need(path.is_file() and not any(p.is_symlink() for p in (path,*path.parents)) and path.stat().st_size<8*1024*1024,
         'Receipt missing, unsafe or oversized: '+name)
    return json.loads(path.read_text())

def result(value,mode,previous):
    header=dict(schema=1,fixture='privkeyio-deadline-0094' if mode=='baseline' else 'privkeyio-deadline-0094a',mode=mode,regtest_only=True,installer=False)
    if mode=='baseline':
        same(value,dict(header,controls=[dict(profile=p,original_binary=True,held_final_replay_rejected=True,no_core_invoice=True)
            for p in ('btc-cln-v1','xbt-privkeyio-v1')]),'Original binary controls incomplete')
    elif mode=='regression':
        same(value,dict(header,regression=True,**{k:previous[k] for k in ('grants','restore','service')}),
             'Patched engine service regression incomplete')
    else:
        need(set(value)==set(header)|{'cases'},'Deadline result fields differ')
        same({k:value[k] for k in header},header,'Deadline result scope differs')
        need(type(value['cases']) is list and len(value['cases'])==6,'Six funded deadline cases required')
        for row,(direction,name) in zip(value['cases'],[(d,n) for d in ('forward','reverse') for n in ('release','timeout','restart-held')]):
            want=dict(direction=direction,scenario=name,local_watchdog=True,worker_absent_at_boundary=True,
                outgoing_offline_at_boundary=name=='restart-held',closing_restart=name=='restart-held',
                paused_expired_recovery=name=='restart-held',arm_reply_SIGKILL=True,send_reply_SIGKILL=True,
                resolution_reply_SIGKILL=True,close_reply_lost=True,exact_attempt_and_HTLCs=True,one_close=True,one_send=True,
                ten_offchain_balances=True,phase='timeout_verified' if name=='timeout' else 'claim_and_sweep_verified',
                nonterminal_recovery_status=True,scoped_native_https=True)
            need(type(row) is dict and set(row)==set(want)|{'accounting'},'Deadline case fields differ')
            same({k:row[k] for k in want},want,'Deadline case incomplete')
            a=row['accounting'];need(type(a) is dict and set(a)=={'initial_sats','returned_wallet_sats',
                'unspent_anchor_sats','fee_sats','confirmed_transactions','wallet_delta_sats','independent_backend_walk'},'Accounting fields differ')
            need(a['independent_backend_walk'] is True and all(type(a[k]) is int and 0<=a[k]<2100000000000000
                for k in ('initial_sats','returned_wallet_sats','unspent_anchor_sats','fee_sats','confirmed_transactions')),
                'Accounting values invalid')
            need(0<a['fee_sats']<300000 and a['unspent_anchor_sats'] in (0,330,660) and a['confirmed_transactions']>=2
                 and type(a['wallet_delta_sats']) is list and len(a['wallet_delta_sats'])==2
                 and all(type(x) is int for x in a['wallet_delta_sats']), 'Recovery allocation missing')
            need(a['initial_sats']==a['returned_wallet_sats']+a['unspent_anchor_sats']+a['fee_sats']
                 and sum(a['wallet_delta_sats'])+a['unspent_anchor_sats']+a['fee_sats']==300000,'Satoshi totals differ')
    return value
