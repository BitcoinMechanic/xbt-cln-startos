#!/usr/bin/env python3
"""Local one-contract authority and exact-operation RPCs for a reverse pilot.

No generic RPC passthrough. Every mutation has a durable intent. Uncertain sends,
closes and gate resolutions are observed, never submitted a second time.
"""
import json
import os
from pathlib import Path
import secrets
import sys
import time
from reverse_contract import PIN, canonical, digest, hex32, pin_matches, require, route, validate, routed, incoming_pins, sent_amount, FIELDS, timing, REPEAT


from pilot_node import save, load, locked, LocalRPC, RPCError


class Node:
    gate_profile = REPEAT

    def gate_ready(self, gate):
        return gate.get('profile')=='reverse-live-v1' and gate.get('repeat_profile')==REPEAT and gate.get('gate_active') is True
    def __init__(self,root,role,rpc=None,clock=time.time):
        require(role in ('xbt','btc'),'invalid_role')
        self.root=Path(root);self.role=role;self.network='xbt' if role=='xbt' else 'bitcoin'
        self.rpc=rpc or LocalRPC(self.root,self.network);self.clock=clock
        self.path=self.root/'reverse-pilot.json'
    def barrier(self):
        require(not any(os.path.lexists(self.root/n) for n in
            ('forward-pilot-restored.json','reverse-pilot-restored.json','xbt-gate-restored.json','btc-gate-restored.json')),'restored_authority_blocked')
    def identity(self,c):
        self.barrier()
        info=self.rpc('getinfo')
        require(info.get('id')==c['nodes'][self.role] and info.get('network')==self.network
            and not any(k.startswith('warning') for k in info),'identity_unavailable')
        require(type(info.get('blockheight')) is int,'height_unavailable')
        return info
    def channel(self,c,r=None):
        rows=self.rpc('listpeerchannels')['channels'];pin=c['channels'][self.role]
        if self.role=='xbt' and routed(c):
            if r is None and self.path.exists():
                r=load(self.path);require(r['pilot_id']==digest(c),'authority_changed')
            if r and 'publish' in r:
                gate=self.rpc('reverse-status',payment_hash=c['payment_hash'])
                binding=gate.get('binding')
                if 'incoming_pin' in r:
                    require(binding==r['incoming_binding'],'incoming_binding_changed')
                    pin=r['incoming_pin'];require(pin in incoming_pins(c),'incoming_channel_not_authorized')
                elif binding is not None:
                    require(gate.get('phase')=='held' and type(binding) is list and len(binding)==2
                            and type(binding[1]) is int,'incoming_binding_changed')
                    pins=[p for p in incoming_pins(c) if p['short_channel_id']==binding[0]]
                    require(len(pins)==1,'incoming_channel_not_authorized');pin=pins[0]
                    matches=[ch for ch in rows if pin_matches(ch,pin)]
                    require(len(matches)==1,'channel_changed');ch=matches[0]
                    spend=self.spend(c)
                    require(spend.get('binding')==binding and spend.get('payment_hash')==c['payment_hash'], 'incoming_binding_changed')
                    hs=[h for h in ch.get('htlcs',[]) if h.get('direction')=='in' and h.get('id')==binding[1]]
                    require(ch.get('state')=='CHANNELD_NORMAL' and ch.get('peer_connected') is True and len(hs)==1
                            and hs[0].get('payment_hash')==c['payment_hash'] and hs[0].get('amount_msat')==3000000
                            and hs[0].get('expiry')==spend.get('cltv_expiry') and hs[0].get('state')=='RCVD_ADD_ACK_REVOCATION'
                            and hs[0].get('local_trimmed',False) is False,'committed_incoming_htlc_required')
                    # Durable once-only actual channel binding, before controller may send.
                    r.update(incoming_pin=pin,incoming_binding=binding,incoming_expiry=spend['cltv_expiry']);save(self.path,r)
        found=[ch for ch in rows if ch.get('channel_id')==pin['channel_id']]
        require(len(found)==1 and pin_matches(found[0],pin),'channel_changed')
        return found[0]
    def record(self,pilot_id):
        self.barrier();r=load(self.path);validate(r['contract'])
        require(r['pilot_id']==pilot_id==digest(r['contract']) and r['role']==self.role,'authority_changed')
        self.identity(r['contract'])
        return r
    def invoice(self,c,d,deadline):
        expected=dict(valid=True,type='bolt11 invoice',currency='bc',payment_hash=c['payment_hash'],
            payment_secret=c['payment_secret'],payee=c['recipient'],amount_msat=1500000)
        require(all(d.get(k)==v and type(d.get(k)) is type(v) for k,v in expected.items()),'invoice_changed')
        require(type(d.get('created_at')) is int and type(d.get('expiry')) is int
            and d['created_at']<=int(self.clock()) and d['created_at']+d['expiry']>=deadline+60
            and type(d.get('min_final_cltv_expiry')) is int and 1<=d['min_final_cltv_expiry']<=40,'invoice_timing_refused')
    def observe(self,pilot_id):
        r=self.record(pilot_id);c=r['contract']
        info=self.identity(c);channel=self.channel(c,r)
        result=dict(pilot_id=pilot_id,node_id=info['id'],network=self.network,blockheight=info['blockheight'],
            channel=channel,outputs=self.rpc('listfunds').get('outputs'),
            intents={key:r[key] for key in ('send','close','release','fail') if key in r})
        if self.role=='btc':
            result['payments']=self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')
            result['decoded']=self.rpc('decode',string=c['invoice'])
            if 'send' in r:result['outgoing_htlc']=self.outgoing(r,channel,result['payments'])
        elif 'publish' in r:
            result['terms']=r['publish']['terms']
            result['gate']=self.rpc('reverse-status',payment_hash=c['payment_hash'])
            if result['gate'].get('phase')=='held':
                result['spend']=self.spend(c)
            if 'invoice' in r['publish']:result['invoice']=r['publish']['invoice']
        else:result['gate_profile']=self.rpc('reverse-pilot-info')
        return result
    def intent(self,r,key,value):
        require(key not in r,'mutation_outcome_requires_observation')
        r[key]=value;save(self.path,r)
    def spend(self,c):
        gate=self.rpc('reverse-status',payment_hash=c['payment_hash'])
        require(gate.get('terms',{}).get('contract')==c, 'incoming_terms_changed')
        return dict(gate['terms'],binding=gate.get('binding'),cltv_expiry=gate.get('cltv_expiry'))
    def outgoing(self,r,ch,payments):
        c=r['contract']
        hs=[h for h in ch.get('htlcs',[]) if h.get('direction')=='out' and h.get('payment_hash')==c['payment_hash']]
        require(len(hs)<=1,'outgoing_htlc_ambiguous')
        if hs:
            h=hs[0]
            require(type(h.get('id')) is int and h['id']>=0 and type(h.get('expiry')) is int
                    and h.get('amount_msat')==sent_amount(c),'outgoing_htlc_changed')
            observed=dict(id=h['id'],expiry=h['expiry'],channel=c['channels']['btc'])
            if 'outgoing_htlc' in r:require(r['outgoing_htlc']==observed,'outgoing_htlc_changed')
            elif h.get('state')=='SENT_ADD_ACK_REVOCATION':
                r['outgoing_htlc']=observed;save(self.path,r)
        return r.get('outgoing_htlc')
    def held(self,r):
        c=r['contract'];ch=self.channel(c,r);gate=self.rpc('reverse-status',payment_hash=c['payment_hash'])
        require(gate.get('phase')=='held' and gate.get('payment_hash')==c['payment_hash'],'incoming_not_held')
        binding=gate.get('binding')
        require(type(binding) is list and len(binding)==2 and binding[0]==ch['short_channel_id']
            and type(binding[1]) is int,'incoming_binding_changed')
        spend=self.spend(c)
        expected=dict(payment_hash=c['payment_hash'],binding=binding,xbt_amount_msat=3000000,
            btc_amount_msat=1500000,btc_invoice=c['invoice'],pilot=self.gate_profile)
        require(all(spend.get(k)==v for k,v in expected.items()),'incoming_terms_changed')
        if routed(c): require(spend.get('cltv_expiry')==r.get('incoming_expiry'),'incoming_expiry_changed')
        return binding,spend
    def step(self,pilot_id,operation,preimage=''):
        r=self.record(pilot_id);c=r['contract']
        require(not r.get('revoked') and type(operation) is str and type(preimage) is str,'authority_refused')
        require(preimage=='' or operation=='release','unexpected_preimage')
        if operation=='publish':
            require(self.role=='xbt','wrong_role')
            if 'publish' not in r:
                now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
                require(self.gate_ready(self.rpc('reverse-pilot-info')),'reverse_gate_required')
                budget=timing(c)
                terms=dict(payment_hash=c['payment_hash'],payment_secret=secrets.token_hex(32),xbt_amount_msat=3000000,
                    btc_amount_msat=1500000,btc_invoice=c['invoice'],expires_at=now+120,min_cltv_delta=budget['minimum'],
                    max_cltv_delta=budget['maximum'],pilot=self.gate_profile,contract=c)
                from reverse_invoice import hints,add,unsigned as encode_unsigned
                invoice_hints=hints(c,self.rpc('listpeerchannels')['channels'])
                unsigned=encode_unsigned(c['payment_hash'],terms['payment_secret'],budget['invoice'])
                self.intent(r,'publish',dict(terms=terms,unsigned=add(unsigned,invoice_hints)))
            publication=r['publish'];terms=publication['terms']
            if 'invoice' not in publication:
                # Registration and signing are idempotent for this persisted input.
                # No new quote secret, timestamp or invoice is generated on recovery.
                require(self.rpc('reverse-repeat-register',quote=terms)=={'registered':True},'registration_unknown')
                invoice=self.rpc('signinvoice',invstring=publication['unsigned'])['bolt11']
                d=self.rpc('decode',string=invoice)
                expected=dict(valid=True,currency='xbt',payee=c['nodes']['xbt'],payment_hash=c['payment_hash'],
                    payment_secret=terms['payment_secret'],amount_msat=3000000,min_final_cltv_expiry=timing(c)['invoice'])
                require(all(d.get(k)==v for k,v in expected.items()),'signed_invoice_mismatch')
                publication['invoice']=invoice;save(self.path,r)
            return dict(invoice=publication['invoice'],terms=terms)
        if operation=='send':
            require(self.role=='btc','wrong_role')
            now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
            self.invoice(c,self.rpc('decode',string=c['invoice']),now)
            require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[],'original_attempt_exists')
            ch=self.channel(c)
            require(ch.get('state')=='CHANNELD_NORMAL' and ch.get('peer_connected') is True
                and ch.get('htlcs')==[] and ch.get('spendable_msat',0)>=sent_amount(c),'outgoing_channel_not_ready')
            self.intent(r,'send',dict(payment_hash=c['payment_hash'],groupid=1,partid=0))
            self.rpc('sendpay',route=route(c),payment_hash=c['payment_hash'],payment_secret=c['payment_secret'],
                bolt11=c['invoice'],groupid=1,partid=0)
            return dict(submitted=True)
        require(self.role=='xbt' and operation in ('close','release','fail'),'operation_refused')
        binding,spend=self.held(r)
        if operation=='close':
            ch=self.channel(c,r);height=self.identity(c)['blockheight']
            require(ch.get('state')=='CHANNELD_NORMAL' and type(spend.get('cltv_expiry')) is int
                and 0<spend['cltv_expiry']-height<=144,'close_deadline_not_reached')
            h=[h for h in ch.get('htlcs',[]) if h.get('id')==binding[1] and h.get('direction')=='in']
            require(len(h)==1 and h[0].get('payment_hash')==c['payment_hash'] and h[0].get('amount_msat')==3000000
                and h[0].get('expiry')==spend['cltv_expiry'] and h[0].get('state')=='RCVD_ADD_ACK_REVOCATION'
                and h[0].get('local_trimmed',False) is False,'original_htlc_required')
            self.intent(r,'close',dict(binding=binding,expiry=spend['cltv_expiry']))
            self.rpc('close',id=ch['channel_id'],unilateraltimeout=1)
            return dict(close_requested=True)
        if operation=='fail':
            require('close' not in r and 'release' not in r,'post_close_failure_refused')
            self.intent(r,'fail',dict(binding=binding))
            return self.rpc('reverse-fail',payment_hash=c['payment_hash'],binding=binding)
        import hashlib
        require(hex32(preimage) and hashlib.sha256(bytes.fromhex(preimage)).hexdigest()==c['payment_hash'],'invalid_preimage')
        require('fail' not in r,'failure_already_requested')
        if 'close' in r:require(self.channel(c).get('state')=='ONCHAIN','confirmed_original_close_required')
        self.intent(r,'release',dict(binding=binding))
        return self.rpc('reverse-release',payment_hash=c['payment_hash'],binding=binding,preimage=preimage)

