#!/usr/bin/env python3
"""Local one-contract authority and exact-operation RPCs for a forward pilot.

No generic RPC passthrough. Every mutation has a durable intent. Uncertain sends,
closes and gate resolutions are observed, never submitted a second time.
"""
import contextlib
import fcntl
import json
import os
from pathlib import Path
import secrets
import socket
import stat
import sys
import tempfile
import time
from pilot_contract import PIN, canonical, digest, hex32, pin_matches, require, route, validate, routed, incoming_pins, sent_amount, FIELDS


def save(path,value):
    fd,tmp=tempfile.mkstemp(prefix='.pilot-',dir=path.parent)
    try:
        with os.fdopen(fd,'w') as f:
            f.write(canonical(value)); f.flush(); os.fsync(f.fileno())
        os.replace(tmp,path)
        fd=os.open(path.parent,os.O_RDONLY)
        try:os.fsync(fd)
        finally:os.close(fd)
    finally:
        if os.path.exists(tmp):os.unlink(tmp)


def load(path):
    fd=os.open(path,os.O_RDONLY|os.O_NOFOLLOW)
    with os.fdopen(fd) as f:
        s=os.fstat(f.fileno())
        require(stat.S_ISREG(s.st_mode) and s.st_mode&0o077==0 and s.st_size<=262144,'invalid_record')
        return json.load(f)


@contextlib.contextmanager
def locked(root):
    fd=os.open(root/'forward-pilot.lock',os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
        yield
    finally:os.close(fd)


class RPCError(ValueError):
    def __init__(self,code):
        super().__init__('rpc_unavailable');self.code=code


class LocalRPC:
    def __init__(self,root,network):self.path=root/network/'lightning-rpc'
    def __call__(self,method,**params):
        with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
            sock.settimeout(15);sock.connect(str(self.path))
            sock.sendall(canonical(dict(jsonrpc='2.0',id='pilot',method=method,params=params)).encode()+b'\n\n')
            raw=b''
            while b'\n\n' not in raw:
                part=sock.recv(65536)
                require(part and len(raw)+len(part)<=4194304,'rpc_unavailable')
                raw+=part
            result=json.loads(raw.split(b'\n\n')[0])
            if type(result.get('error')) is dict: raise RPCError(result['error'].get('code'))
            require(type(result.get('result')) is dict,'rpc_unavailable')
            return result['result']


class Node:
    gate_profile = 'live-pilot-v1'

    def gate_ready(self, gate):
        return gate == dict(profile=self.gate_profile, registered_quotes=0)
    def __init__(self,root,role,rpc=None,clock=time.time):
        require(role in ('btc','xbt'),'invalid_role')
        self.root=Path(root);self.role=role;self.network='bitcoin' if role=='btc' else 'xbt'
        self.rpc=rpc or LocalRPC(self.root,self.network);self.clock=clock
        self.path=self.root/'forward-pilot.json'
    def barrier(self):
        require(not any(os.path.lexists(self.root/n) for n in
            ('forward-pilot-restored.json','btc-gate-restored.json','xbt-gate-restored.json')),'restored_authority_blocked')
    def identity(self,c):
        self.barrier()
        info=self.rpc('getinfo')
        require(info.get('id')==c['nodes'][self.role] and info.get('network')==self.network
            and not any(k.startswith('warning') for k in info),'identity_unavailable')
        require(type(info.get('blockheight')) is int,'height_unavailable')
        return info
    def channel(self,c,r=None):
        rows=self.rpc('listpeerchannels')['channels'];pin=c['channels'][self.role]
        if self.role=='btc' and routed(c):
            if r is None and self.path.exists():
                r=load(self.path);require(r['pilot_id']==digest(c),'authority_changed')
            if r and 'publish' in r:
                gate=self.rpc('xbt-quote-status',payment_hash=c['payment_hash'])
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
                    spend=self.rpc('xbt-spend-info',payment_hash=c['payment_hash'])
                    require(spend.get('binding')==binding and spend.get('payment_hash')==c['payment_hash'], 'incoming_binding_changed')
                    hs=[h for h in ch.get('htlcs',[]) if h.get('direction')=='in' and h.get('id')==binding[1]]
                    require(ch.get('state')=='CHANNELD_NORMAL' and ch.get('peer_connected') is True and len(hs)==1
                            and hs[0].get('payment_hash')==c['payment_hash'] and hs[0].get('amount_msat')==1000000
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
    def authorize(self,c,confirmed):
        require(confirmed is True,'confirmation_required');validate(c);require(not routed(c),'routed_session_required');self.identity(c)
        now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
        pilot_id=digest(c)
        if self.path.exists():
            r=self.record(pilot_id)
            require(r.get('rune') and not r.get('revoked'),'authority_unavailable')
            return dict(pilot_id=pilot_id,rune=r['rune'],payment_started='send' in r)
        channel=self.channel(c)
        require(channel.get('state')=='CHANNELD_NORMAL' and channel.get('peer_connected') is True
            and channel.get('htlcs')==[],'channel_not_ready')
        if self.role=='btc':
            gate=self.rpc('xbt-pilot-info')
            require(self.gate_ready(gate),'unused_live_gate_required')
        else:
            decoded=self.rpc('decode',string=c['invoice'])
            self.invoice(c,decoded,now+120)
            require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[],'outgoing_already_exists')
        r=dict(schema=1,role=self.role,pilot_id=pilot_id,contract=c,credential_intent=True)
        save(self.path,r) # A lost mint reply never creates another authority.
        restrictions=[['method=swap-pilot-observe','method=swap-pilot-step'],['pnamepilot_id='+pilot_id]]
        result=self.rpc('createrune',restrictions=restrictions)
        require(type(result.get('rune')) is str and result.get('unique_id') is not None,'credential_reply_unknown')
        r.update(rune=result['rune'],unique_id=result['unique_id']);save(self.path,r)
        return dict(pilot_id=pilot_id,rune=r['rune'],payment_started=False)
    def invoice(self,c,d,deadline):
        expected=dict(valid=True,type='bolt11 invoice',currency='xbt',payment_hash=c['payment_hash'],
            payment_secret=c['payment_secret'],payee=c['recipient'],amount_msat=2000000)
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
        if self.role=='xbt':
            result['payments']=self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')
            result['decoded']=self.rpc('decode',string=c['invoice'])
        elif 'publish' in r:
            result['terms']=r['publish']['terms']
            result['gate']=self.rpc('xbt-quote-status',payment_hash=c['payment_hash'])
            if result['gate'].get('phase')=='held':
                result['spend']=self.rpc('xbt-spend-info',payment_hash=c['payment_hash'])
            if 'invoice' in r['publish']:result['invoice']=r['publish']['invoice']
        else:result['gate_profile']=self.rpc('xbt-pilot-info')
        return result
    def intent(self,r,key,value):
        require(key not in r,'mutation_outcome_requires_observation')
        r[key]=value;save(self.path,r)
    def held(self,r):
        c=r['contract'];ch=self.channel(c,r);gate=self.rpc('xbt-quote-status',payment_hash=c['payment_hash'])
        require(gate.get('phase')=='held' and gate.get('payment_hash')==c['payment_hash'],'incoming_not_held')
        binding=gate.get('binding')
        require(type(binding) is list and len(binding)==2 and binding[0]==ch['short_channel_id']
            and type(binding[1]) is int,'incoming_binding_changed')
        spend=self.rpc('xbt-spend-info',payment_hash=c['payment_hash'])
        expected=dict(payment_hash=c['payment_hash'],binding=binding,btc_amount_msat=1000000,
            xbt_amount_msat=2000000,xbt_invoice=c['invoice'],pilot=self.gate_profile)
        require(all(spend.get(k)==v for k,v in expected.items()),'incoming_terms_changed')
        if routed(c): require(spend.get('cltv_expiry')==r.get('incoming_expiry'),'incoming_expiry_changed')
        return binding,spend
    def step(self,pilot_id,operation,preimage=''):
        r=self.record(pilot_id);c=r['contract']
        require(not r.get('revoked') and type(operation) is str and type(preimage) is str,'authority_refused')
        require(preimage=='' or operation=='release','unexpected_preimage')
        if operation=='publish':
            require(self.role=='btc','wrong_role')
            if 'publish' in r:
                require('invoice' in r['publish'],'publication_outcome_requires_inspection')
                return dict(invoice=r['publish']['invoice'],terms=r['publish']['terms'])
            now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
            require(self.gate_ready(self.rpc('xbt-pilot-info')),'unused_live_gate_required')
            terms=dict(payment_hash=c['payment_hash'],payment_secret=secrets.token_hex(32),btc_amount_msat=1000000,
                xbt_amount_msat=2000000,xbt_invoice=c['invoice'],expires_at=now+120,min_cltv_delta=288,
                max_cltv_delta=2016,pilot=self.gate_profile)
            invoice_hints=None
            if routed(c):
                from routed_invoice import hints
                invoice_hints=hints(c,self.rpc('listpeerchannels')['channels'])
            self.intent(r,'publish',dict(terms=terms))
            require(self.rpc('xbt-register',quote=terms)=={'registered':True},'registration_unknown')
            from swap_invoice import unsigned_invoice
            unsigned=unsigned_invoice(c['payment_hash'],terms['payment_secret'],1000000,120,currency='bc',final_cltv=300)
            if invoice_hints is not None:
                from routed_invoice import add
                unsigned=add(unsigned,invoice_hints)
            invoice=self.rpc('signinvoice',invstring=unsigned)['bolt11']
            d=self.rpc('decode',string=invoice)
            expected=dict(valid=True,currency='bc',payee=c['nodes']['btc'],payment_hash=c['payment_hash'],
                payment_secret=terms['payment_secret'],amount_msat=1000000,min_final_cltv_expiry=300)
            require(all(d.get(k)==v for k,v in expected.items()),'signed_invoice_mismatch')
            r['publish']['invoice']=invoice;save(self.path,r)
            return dict(invoice=invoice,terms=terms)
        if operation=='send':
            require(self.role=='xbt','wrong_role')
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
        require(self.role=='btc' and operation in ('close','release','fail'),'operation_refused')
        binding,spend=self.held(r)
        if operation=='close':
            ch=self.channel(c,r);height=self.identity(c)['blockheight']
            require(ch.get('state')=='CHANNELD_NORMAL' and type(spend.get('cltv_expiry')) is int
                and 0<spend['cltv_expiry']-height<=72,'close_deadline_not_reached')
            h=[h for h in ch.get('htlcs',[]) if h.get('id')==binding[1] and h.get('direction')=='in']
            require(len(h)==1 and h[0].get('payment_hash')==c['payment_hash'] and h[0].get('amount_msat')==1000000
                and h[0].get('expiry')==spend['cltv_expiry'] and h[0].get('state')=='RCVD_ADD_ACK_REVOCATION'
                and h[0].get('local_trimmed',False) is False,'original_htlc_required')
            self.intent(r,'close',dict(binding=binding,expiry=spend['cltv_expiry']))
            self.rpc('close',id=ch['channel_id'],unilateraltimeout=1)
            return dict(close_requested=True)
        if operation=='fail':
            require('close' not in r and 'release' not in r,'post_close_failure_refused')
            self.intent(r,'fail',dict(binding=binding))
            return self.rpc('xbt-fail',payment_hash=c['payment_hash'],binding=binding)
        import hashlib
        require(hex32(preimage) and hashlib.sha256(bytes.fromhex(preimage)).hexdigest()==c['payment_hash'],'invalid_preimage')
        require('fail' not in r,'failure_already_requested')
        if 'close' in r:require(self.channel(c).get('state')=='ONCHAIN','confirmed_original_close_required')
        self.intent(r,'release',dict(binding=binding))
        return self.rpc('xbt-release-bound',payment_hash=c['payment_hash'],preimage=preimage)


def plugin(root,role):
    node=Node(root,role)
    for line in sys.stdin:
        if not line.strip():continue
        msg=json.loads(line);method=msg.get('method');request_id=msg.get('id')
        if request_id is None:continue
        try:
            if method=='getmanifest':
                result=dict(options=[],rpcmethods=[dict(name='swap-pilot-observe',usage='pilot_id',description='Inspect one locally authorized pilot'),
                    dict(name='swap-pilot-step',usage='pilot_id operation preimage',description='Execute one exact locally authorized pilot operation')],
                    subscriptions=[],hooks=[],dynamic=False,nonnumericids=True)
                result['rpcmethods'].append(dict(name='swap-session-call', usage='session_id operation contract pilot_id preimage', description='Bounded repeat swap authority'))
            elif method=='init':
                require(msg['params']['configuration']['network']==node.network,'wrong_network');result={}
            else:
                p=msg['params'];require(type(p) is dict,'named_parameters_required')
                with locked(root):
                    if method=='swap-session-call':
                        require(set(p)=={'session_id','operation','contract','pilot_id','preimage'},'invalid_parameters')
                        from swap_session import Session
                        result=Session(root,role).call(**p)
                    elif method=='swap-pilot-observe':
                        require(set(p)=={'pilot_id'},'invalid_parameters');result=node.observe(**p)
                    else:
                        require(method=='swap-pilot-step' and set(p)=={'pilot_id','operation','preimage'},'invalid_parameters')
                        result=node.step(**p)
            reply=dict(jsonrpc='2.0',id=request_id,result=result)
        except Exception:reply=dict(jsonrpc='2.0',id=request_id,error=dict(code=-32602,message='Pilot operation refused or uncertain; inspect pilot status.'))
        print(canonical(reply)+'\n',flush=True)


def main():
    os.umask(0o077)
    # Pinned invoice encoder is image-owned, never loaded from a volume.
    sys.path.insert(0,'/usr/local/libexec/cln-swap')
    role=sys.argv[1];root=Path(sys.argv[2]);mode=sys.argv[3]
    if mode=='plugin':plugin(root,role);return
    require(mode=='authorize','invalid_operation')
    request=json.loads(sys.stdin.read(262145))
    with locked(root):result=Node(root,role).authorize(request['contract'],request.get('confirmed'))
    print(canonical(result))


if __name__=='__main__':
    try:main()
    except Exception:
        print('{"error":"pilot_authority_refused_or_uncertain"}')
        raise SystemExit(1) from None
