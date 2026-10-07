"""Locally enabled, channel-pinned repeat authority. No raw RPC passthrough.

Enrollment consumes a durable slot before any operation is exposed. Expiry and
pause block new enrollment; enrolled swaps keep their original recovery rights.
Old sessions and all mutation records survive renewal and service restarts.
"""
import json
import os
from pathlib import Path
import secrets
import sys
import time
from pilot_contract import digest, hex32, pin_matches, require, validate
from pilot_node import Node, load, locked, save

PROFILE = 'startos-fixed-repeat-v1'
FIELDS = ('channel_id','short_channel_id','funding_txid','funding_outnum','peer_id')


def folder(root, name):
    path = root / name
    require(not path.is_symlink(), 'invalid_session_directory')
    path.mkdir(mode=0o700, exist_ok=True)
    return path


class RepeatNode(Node):
    gate_profile = PROFILE
    def __init__(self, root, role, pilot_id, rpc=None, clock=time.time):
        require(hex32(pilot_id), 'invalid_swap_id')
        super().__init__(root, role, rpc, clock)
        self.path = folder(self.root, 'forward-swaps') / (pilot_id + '.json')
    def gate_ready(self, gate):
        return gate.get('profile') == PROFILE and type(gate.get('registered_quotes')) is int


class Session:
    gate_profile = PROFILE
    def __init__(self, root, role, rpc=None, clock=time.time):
        self.node = Node(root, role, rpc, clock)
        self.root = self.node.root; self.role = role; self.rpc = self.node.rpc; self.clock = clock
    def sessions(self): return folder(self.root, 'forward-sessions')
    def records(self): return folder(self.root, 'forward-swaps')
    def read(self, session_id):
        self.node.barrier(); require(hex32(session_id), 'invalid_session_id')
        s = load(self.sessions() / (session_id + '.json'))
        require(s['session_id'] == session_id and s['role'] == self.role, 'session_identity_changed')
        info = self.rpc('getinfo')
        require(info.get('id') == s['node_id'] and info.get('network') == self.node.network
                and not any(k.startswith('warning') for k in info), 'session_identity_changed')
        return s
    def write(self, s): save(self.sessions() / (s['session_id'] + '.json'), s)
    def terminal(self, r):
        c = validate(r['contract']); self.node.identity(c)
        ch = self.node.channel(c)
        require(ch.get('state') == 'CHANNELD_NORMAL' and ch.get('htlcs') == []
                and 'close' not in r, 'previous_swap_requires_recovery')
        if self.role == 'btc':
            require('publish' in r, 'previous_enrollment_unfinished')
            g = self.rpc('xbt-quote-status', payment_hash=c['payment_hash'])
            if 'retire' in r:
                require(g.get('payment_hash')==c['payment_hash'] and g.get('phase')=='expired' and g.get('binding') is None, 'retirement_unconfirmed')
                return
            require(g.get('payment_hash') == c['payment_hash'] and g.get('phase') in ('resolved','failed')
                    and type(g.get('binding')) is list
                    and g['binding'][0] == c['channels']['btc']['short_channel_id'], 'previous_gate_not_terminal')
            require(('release' in r and g['phase'] == 'resolved') or ('fail' in r and g['phase'] == 'failed'),
                    'previous_resolution_unknown')
        else:
            p = self.rpc('listsendpays', payment_hash=c['payment_hash']).get('payments')
            if 'retire' in r:
                require('send' not in r and p==[], 'retired_outgoing_changed');return
            require('send' in r and type(p) is list and len(p) == 1, 'previous_attempt_unknown')
            p = dict(p[0]); p.setdefault('partid', 0)
            require(all(type(p.get(k)) is type(v) and p.get(k) == v for k,v in
                        dict(payment_hash=c['payment_hash'],groupid=1,partid=0,amount_sent_msat=2000000).items())
                    and p.get('status') in ('complete','failed'), 'previous_attempt_not_terminal')
            if p['status']=='complete':
                import hashlib
                require(hex32(p.get('payment_preimage')) and hashlib.sha256(bytes.fromhex(p['payment_preimage'])).hexdigest()==c['payment_hash'], 'previous_preimage_invalid')
            else: require(not p.get('payment_preimage'), 'contradictory_previous_outcome')
    def prior(self, except_id=None):
        if self.node.path.exists(): self.terminal(load(self.node.path))
        for path in self.records().glob('*.json'):
            if path.stem != except_id: self.terminal(load(path))
        # A reserved slot with no complete record must never be silently skipped.
        for path in self.sessions().glob('*.json'):
            s = load(path)
            for pilot_id in s['enrolled']:
                require((self.records()/(pilot_id+'.json')).exists() or pilot_id == except_id,
                        'enrollment_outcome_unknown')
    def enable(self, channel_id, max_swaps, confirmed, new_grant=False):
        require(confirmed is True and type(new_grant) is bool, 'confirmation_required')
        require(type(max_swaps) is int and 1 <= max_swaps <= 10, 'invalid_swap_limit')
        self.node.barrier()
        active = self.root/'forward-session.json'
        if active.exists() and not new_grant:
            s = self.read(load(active)['session_id'])
            require((not channel_id or s['channel']['short_channel_id'] == channel_id)
                    and s['max_swaps'] == max_swaps and s.get('rune'), 'existing_grant_differs_or_uncertain')
            return self.grant(s)
        self.prior()
        info = self.rpc('getinfo')
        require(info.get('network') == self.node.network and not any(k.startswith('warning') for k in info), 'identity_unavailable')
        rows = self.rpc('listpeerchannels').get('channels')
        require(type(rows) is list, 'invalid_channels')
        choices = [r for r in rows if r.get('state') == 'CHANNELD_NORMAL' and r.get('peer_connected') is True
                   and r.get('htlcs') == [] and (not channel_id or r.get('short_channel_id') == channel_id)]
        require(len(choices) == 1, 'choose_one_connected_channel')
        pin = {k:choices[0][k] for k in FIELDS}
        now = int(self.clock()); session_id = secrets.token_hex(32)
        s = dict(schema=1, session_id=session_id, role=self.role, node_id=info['id'], channel=pin,
                 created_at=now, expires_at=now+86400, max_swaps=max_swaps, enrolled={}, paused=False,
                 credential_intent=True)
        self.write(s); save(active, {'session_id':session_id})
        # Restrict method, named parameter set and this grant ID on the CLN server.
        restrictions = [['method=swap-session-call'], ['pnamesession_id='+session_id], ['pnum=5']]
        result = self.rpc('createrune', restrictions=restrictions)
        require(type(result.get('rune')) is str and result.get('unique_id') is not None, 'credential_reply_unknown')
        s.update(rune=result['rune'], unique_id=result['unique_id']); self.write(s)
        self.enable_gate()
        return self.grant(s)
    def enable_gate(self):
        if self.role == 'btc':
            from gate import record, RECORD
            activation = record(self.root)
            activation['profile'] = PROFILE
            save(self.root/RECORD, activation)
    def grant(self, s):
        # Retry of the local setup also completes a crash before gate opt-in.
        self.enable_gate()
        return dict(session_id=s['session_id'], credential=json.dumps({'session_id':s['session_id'],'rune':s['rune']},separators=(',',':')),
                    max_swaps=s['max_swaps'], expires_at=s['expires_at'],
                    restart_required=self.role=='btc' and self.rpc('xbt-pilot-info').get('profile') != PROFILE,
                    payment_started=False)
    def pause(self):
        s=self.read(load(self.root/'forward-session.json')['session_id']);s['paused']=True;self.write(s)
        return dict(paused=True, recovery_preserved=True)
    def enroll(self, s, c):
        validate(c); pilot_id=digest(c)
        node=RepeatNode(self.root,self.role,pilot_id,self.rpc,self.clock)
        require(c['nodes'][self.role] == s['node_id'] and c['channels'][self.role] == s['channel'], 'outside_session_channel')
        # Idempotence is exact and works after expiry/pause; it never reserves again.
        if pilot_id in s['enrolled']:
            require(s['enrolled'][pilot_id] == c['payment_hash'], 'enrollment_changed')
            if node.path.exists():
                r=node.record(pilot_id);require(r['session_id']==s['session_id'],'enrollment_changed')
                return dict(pilot_id=pilot_id)
        else:
            require(load(self.root/'forward-session.json')['session_id'] == s['session_id']
                    and not s['paused'] and s['created_at'] <= int(self.clock()) < s['expires_at'], 'session_closed')
            require(len(s['enrolled']) < s['max_swaps'], 'session_limit_reached')
            self.prior()
            require(not node.path.exists(), 'swap_already_enrolled')
            all_records = [load(p) for p in self.records().glob('*.json')]
            if self.node.path.exists(): all_records.append(load(self.node.path))
            require(not any(r['contract']['payment_hash']==c['payment_hash'] for r in all_records), 'payment_hash_reused')
            now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
            node.identity(c);ch=node.channel(c)
            require(ch.get('state')=='CHANNELD_NORMAL' and ch.get('peer_connected') is True and ch.get('htlcs')==[], 'channel_not_ready')
            if self.role=='xbt':
                node.invoice(c,self.rpc('decode',string=c['invoice']),now+120)
                require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[], 'outgoing_already_exists')
            else: require(node.gate_ready(self.rpc('xbt-pilot-info')), 'restart_btc_for_repeat_gate')
            s['enrolled'][pilot_id]=c['payment_hash'];self.write(s)
        # If power failed after reservation, retry can only finish this exact record.
        save(node.path, dict(schema=1,role=self.role,pilot_id=pilot_id,contract=c,session_id=s['session_id']))
        return dict(pilot_id=pilot_id)
    def call(self, session_id, operation, contract, pilot_id, preimage):
        require(type(operation) is str and type(contract) is str and type(pilot_id) is str
                and type(preimage) is str, 'invalid_parameters')
        s=self.read(session_id)
        if operation=='info':
            require(contract==pilot_id==preimage=='','invalid_parameters')
            return dict(session_id=session_id,node_id=s['node_id'],network=self.node.network,channel=s['channel'],
                        remaining=s['max_swaps']-len(s['enrolled']),expires_at=s['expires_at'],paused=s['paused'],
                        current=load(self.root/'forward-session.json')['session_id']==session_id,
                        gate_ready=self.role!='btc' or RepeatNode.gate_ready(self,self.rpc('xbt-pilot-info')))
        if operation=='enroll':
            require(pilot_id==preimage=='' and len(contract)<=32768,'invalid_parameters')
            return self.enroll(s,json.loads(contract))
        require(contract=='' and hex32(pilot_id) and pilot_id in s['enrolled'], 'swap_not_enrolled')
        node=RepeatNode(self.root,self.role,pilot_id,self.rpc,self.clock)
        require(node.record(pilot_id)['session_id']==session_id,'enrollment_changed')
        if operation=='observe':
            require(preimage=='','invalid_parameters');return node.observe(pilot_id)
        if operation=='retire':
            require(preimage=='','invalid_parameters')
            r=node.record(pilot_id)
            require(not any(k in r for k in ('send','close','release','fail')),'retirement_refused')
            if self.role=='btc':
                require('publish' in r and r['publish']['terms']['expires_at']<=int(self.clock()),'quote_not_expired')
                g=self.rpc('xbt-quote-status',payment_hash=r['contract']['payment_hash'])
                require(g.get('phase') in ('quoted','expired') and g.get('binding') is None,'quote_was_accepted')
                if 'retire' not in r:node.intent(r,'retire',True)
                if g['phase']!='expired':
                    require(self.rpc('xbt-retire-repeat',payment_hash=r['contract']['payment_hash'])=={'retired':True},'retirement_unknown')
            else:
                require(self.rpc('listsendpays',payment_hash=r['contract']['payment_hash']).get('payments')==[], 'outgoing_already_exists')
                if 'retire' not in r:node.intent(r,'retire',True)
            return {'retired':True}
        require(operation in ('publish','send','close','release','fail'),'operation_refused')
        if operation in ('publish','send'):require('retire' not in node.record(pilot_id),'retired_swap')
        return node.step(pilot_id,operation,preimage)


def main():
    os.umask(0o077);role,root,mode=sys.argv[1],Path(sys.argv[2]),sys.argv[3]
    raw=sys.stdin.read(32769);require(len(raw)<=32768,'request_too_large')
    request=json.loads(raw)
    with locked(root):
        session=Session(root,role)
        if mode=='enable':
            require(set(request)=={'channel','maxSwaps','confirmed','newGrant'},'invalid_request')
            result=session.enable(request['channel'],request['maxSwaps'],request['confirmed'],request['newGrant'])
        else:
            require(mode=='pause' and request=={'confirmed':True},'confirmation_required');result=session.pause()
    print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as error:
        safe={'restored_authority_blocked','choose_one_connected_channel','previous_swap_requires_recovery','previous_gate_not_terminal','previous_attempt_not_terminal','previous_enrollment_unfinished','existing_grant_differs_or_uncertain','invalid_swap_limit'}
        reason=str(error) if isinstance(error,ValueError) and str(error) in safe else 'session_refused_or_uncertain'
        print(json.dumps(dict(error=reason)));raise SystemExit(1) from None
