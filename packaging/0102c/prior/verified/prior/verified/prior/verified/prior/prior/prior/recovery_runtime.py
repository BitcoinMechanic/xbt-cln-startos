"""Funded recovery evidence; historical node/UI and swap proofs stay separate."""
import json
from pathlib import Path
import re
import node_ui_runtime as node_ui
import recovery_result as recovery

BUNDLE=Path(__file__).resolve().parent
require=node_ui.require
same=node_ui.same
PRIOR_EXPORT='1289690e376b402a7a46bff1c52d478bbfaca6c029df7b3749a2f92d41ccc5d6'


def matches(value,pattern):return type(value) is str and re.fullmatch(pattern,value) is not None

def integer(value):return type(value) is int


def validate(e):
    require(type(e) is dict and set(e)=={'schema','fixture','source','engine_fix','withdrawal_fees',
        'engine_image','fixture_image','hooks_sha256','result','accounting','retained','regtest_only','installer'},
        'Recovery evidence fields differ')
    same({k:e[k] for k in ('schema','fixture','regtest_only','installer')},
         dict(schema=1,fixture='0088',regtest_only=True,installer=False),'Recovery scope differs')
    recovery.validate(e['result'])
    retained=e['retained']
    require(type(retained) is dict and set(retained)=={'schema','export_sha256','original_evidence',
        'retained_swap_cases','retained_ui_payments'},'Retained export fields differ')
    same({k:retained[k] for k in ('schema','export_sha256','retained_swap_cases','retained_ui_payments')},
         dict(schema=1,export_sha256=PRIOR_EXPORT,retained_swap_cases=30,retained_ui_payments=4),
         'Retained 0087 export differs')
    old=retained['original_evidence'];node_ui.validate(old)
    source=e['source'];require(type(source) is dict,'Recovery source missing')
    manifest=json.loads((BUNDLE/'retained-0089-source-manifest.json').read_text())
    wanted=json.loads((BUNDLE/'expected-build-source.json').read_text())
    checkpoints=source.get('checkpoints')
    require(type(checkpoints) is dict and set(checkpoints)==set(manifest) and
            all(matches(v,'[0-9a-f]{40}') for v in checkpoints.values()),'Tested checkpoints differ')
    same(source,dict(wanted,checkpoints=checkpoints,parent_image=old['images']['fixture'],
                     backend_sha256=old['backend_sha256']),'Recovery source receipt differs')
    require(checkpoints['lightning']==wanted['source_lock']['engine']['commit'],'Pinned engine checkpoint differs')
    same({k:v for k,v in wanted['source_lock'].items() if k!='engine_patch'},old['source']['source_lock'],
         'Retained engine/UI base changed')
    require(wanted['package_tree']==manifest['xbt-cln-startos']['tree'] and
            wanted['files']==manifest['xbt-cln-startos']['files'],'Expected source manifest differs')
    require(all(matches(e[k],'sha256:[0-9a-f]{64}') for k in ('engine_image','fixture_image')) and
            len({e['engine_image'],e['fixture_image'],source['parent_image']})==3,'Image proof differs')
    require(matches(e['hooks_sha256'],'[0-9a-f]{64}'),'Compiled hook proof missing')
    engine=e['engine_fix']
    require(type(engine) is dict and set(engine)=={'engine_patch','binary_sha256','controls'},'Engine proof fields differ')
    same(engine['engine_patch'],wanted['source_lock']['engine_patch'],'Engine patch/test proof differs')
    require(matches(engine['binary_sha256'],'[0-9a-f]{64}'),'Engine binary proof missing')
    require(type(engine['controls']) is dict and set(engine['controls'])=={'baseline','patched'},'Engine controls missing')
    csvs=[1,16,17,127,128,4032,32767]
    for name in ('baseline','patched'):
        rows=engine['controls'][name]
        require(type(rows) is list and len(rows)==7,'Engine witness cases missing')
        for row,csv in zip(rows,csvs):
            require(type(row) is dict and set(row)=={'csv','script','signature','actual','estimated'} and
                    all(integer(v) for v in row.values()),'Witness fields differ')
            require(row['csv']==csv and row['script']==(37 if csv<=16 else 38 if csv<=127 else 39) and
                    69<=row['signature']<=71 and row['actual']==164+1+1+row['signature']+1+row['script'],
                    'Serialized witness differs')
            require(row['estimated']==(239 if name=='baseline' else 277) and
                    (row['estimated']<row['actual'] if name=='baseline' else row['estimated']>=row['actual']),
                    'Original/patched estimator control differs')
    fees=e['withdrawal_fees']
    require(type(fees) is list and len(fees)==3,'Three default-fee withdrawals required')
    for row,name in zip(fees,('restored','receiver-peer','opener-peer')):
        require(type(row) is dict and set(row)=={'node','fee_sats','weight','vsize','default_feerate'} and
                row['node']==name and row['default_feerate'] is True and
                all(integer(row[k]) and row[k]>0 for k in ('fee_sats','weight','vsize')) and
                row['vsize']==(row['weight']+3)//4,'Default-fee withdrawal proof differs')
    a=e['accounting']
    require(type(a) is dict and set(a)=={'deposits','funding','closing','original_channel_balances',
                                      'withdrawals','remaining_anchors'},'Accounting fields differ')
    deposits=a['deposits']
    require(type(deposits) is list and len(deposits)==4,'Deposits missing')
    for row in deposits:
        require(type(row) is dict and set(row)=={'txid','vout','sats'} and matches(row['txid'],'[0-9a-f]{64}') and
                integer(row['vout']) and row['vout']>=0 and integer(row['sats']) and row['sats']>0,'Deposit fields differ')
    require(len({(r['txid'],r['vout']) for r in deposits})==4 and
            sorted(r['sats'] for r in deposits)==[12345,23456,400000,1000000] and
            sum(r['sats'] for r in deposits)==e['result']['deposited_sats'],'Deposit accounting differs')
    for name,count in [('funding',2),('withdrawals',3)]:
        require(type(a[name]) is list and len(a[name])==count and len(set(a[name]))==count and
                all(matches(v,'[0-9a-f]{64}') for v in a[name]),'Transaction proof differs: '+name)
    require(type(a['closing']) is dict and set(a['closing'])==set(a['funding']) and
            len(set(a['closing'].values()))==2 and all(matches(v,'[0-9a-f]{64}') for v in a['closing'].values()),
            'Both original funding outputs must close')
    require(type(a['original_channel_balances']) is dict and set(a['original_channel_balances'])==set(a['funding']) and
            all(integer(v) and v>0 for v in a['original_channel_balances'].values()),'Recovered owner allocations missing')
    anchors=a['remaining_anchors']
    require(type(anchors) is list and len(anchors)<=4,'Anchor residue differs')
    for row in anchors:
        require(type(row) is dict and set(row)=={'txid','vout','sats'} and row['txid'] in a['closing'].values() and
                integer(row['vout']) and row['vout']>=0 and type(row['sats']) is int and row['sats']==330,
                'Unexpected unrecovered residue')
    require(len({(r['txid'],r['vout']) for r in anchors})==len(anchors) and
            sum(r['sats'] for r in anchors)==e['result']['unspent_anchor_sats'],'Anchor accounting differs')
    require(sum(r['fee_sats'] for r in fees)<=e['result']['mining_fees_sats'],'Withdrawal fees exceed confirmed total')
