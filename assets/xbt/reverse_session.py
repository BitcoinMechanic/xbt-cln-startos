import market_terms as mt
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
from reverse_contract import digest, hex32, pin_matches, require, validate, routed, incoming_pins, sent_amount, GRANT_LIMITS, route_limit
from reverse_node import Node, load, locked, save

PROFILE = 'startos-reverse-repeat-v1'
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
        self.path = folder(self.root, 'reverse-swaps') / (pilot_id + '.json')
    def gate_ready(self, gate):
        return gate.get('profile') == 'reverse-live-v1' and gate.get('repeat_profile') == PROFILE and gate.get('gate_active') is True


class Session:
    gate_profile = PROFILE
    def __init__(self, root, role, rpc=None, clock=time.time):
        self.node = Node(root, role, rpc, clock)
        self.root = self.node.root; self.role = role; self.rpc = self.node.rpc; self.clock = clock
    def sessions(self): return folder(self.root, 'reverse-sessions')
    def records(self): return folder(self.root, 'reverse-swaps')
    def read(self, session_id):
        self.node.barrier(); require(hex32(session_id), 'invalid_session_id')
        s = load(self.sessions() / (session_id + '.json'))
        require(s['session_id'] == session_id and s['role'] == self.role and s.get('profile') in GRANT_LIMITS, 'session_identity_changed')
        info = self.rpc('getinfo')
        require(info.get('id') == s['node_id'] and info.get('network') == self.node.network
                and not any(k.startswith('warning') for k in info), 'session_identity_changed')
        return s
    def write(self, s): save(self.sessions() / (s['session_id'] + '.json'), s)
    def terminal_channel(self, c, r, pin, binding=None):
        """Check historical settlement without requiring an old channel to stay open.

        Never select a replacement channel. A non-normal retained channel needs
        the original HTLC's terminal wallet state; an archived channel must match
        every funding pin. CLN archives only after full on-chain resolution.
        """
        rows = self.rpc('listpeerchannels').get('channels')
        require(type(rows) is list, 'invalid_channels')
        matches = [ch for ch in rows if ch.get('channel_id') == pin['channel_id']]
        if not matches:
            closed = self.rpc('listclosedchannels').get('closedchannels')
            require(type(closed) is list, 'previous_channel_history_unavailable')
            matches = [ch for ch in closed if ch.get('channel_id') == pin['channel_id']]
            require(len(matches) == 1 and pin_matches(matches[0], pin), 'previous_channel_history_unavailable')
            return
        require(len(matches) == 1 and pin_matches(matches[0], pin), 'channel_changed')
        ch = matches[0]
        require(ch.get('htlcs') == [], 'previous_swap_requires_recovery')
        if ch.get('state') == 'CHANNELD_NORMAL': return
        require(ch.get('state') in ('CHANNELD_SHUTTING_DOWN', 'CLOSINGD_SIGEXCHANGE',
                'CLOSINGD_COMPLETE', 'AWAITING_UNILATERAL', 'FUNDING_SPEND_SEEN', 'ONCHAIN'),
                'previous_swap_requires_recovery')
        history = self.rpc('listhtlcs', id=pin['channel_id']).get('htlcs')
        require(type(history) is list, 'previous_htlc_not_terminal')
        found = [h for h in history if h.get('payment_hash') == c['payment_hash']]
        if 'retire' in r:
            require(found == [], 'retired_outgoing_changed' if self.role == 'btc' else 'retirement_unconfirmed')
            return
        expected = dict(short_channel_id=pin['short_channel_id'], payment_hash=c['payment_hash'],
                        direction='in' if self.role == 'xbt' else 'out',
                        amount_msat=mt.amounts(c)['xbt'] if self.role == 'xbt' else sent_amount(c),
                        state='SENT_REMOVE_ACK_REVOCATION' if self.role == 'xbt' else 'RCVD_REMOVE_ACK_REVOCATION')
        if self.role == 'xbt':
            expected['id'] = binding[1]
            if routed(c): expected['expiry'] = r['incoming_expiry']
        require(len(found) == 1 and all(type(found[0].get(k)) is type(v) and found[0].get(k) == v
                for k,v in expected.items()), 'previous_htlc_not_terminal')
    def terminal(self, r):
        c = validate(r['contract']); self.node.identity(c)
        require(r.get('pilot_id') == digest(c) and r.get('role') == self.role, 'authority_changed')
        require('close' not in r, 'previous_swap_requires_recovery')
        pin = c['channels'][self.role]; binding = None
        if r.get('unpublished_retired') is True:
            require(mt.market(c) and r.get('retire') is True and not any(k in r for k in ('publish','send','release','fail','close')), 'retirement_refused')
            require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[], 'retirement_refused')
            self.terminal_channel(c,r,pin)
            return
        if self.role == 'xbt':
            require('publish' in r, 'previous_enrollment_unfinished')
            g = self.rpc('reverse-status', payment_hash=c['payment_hash'])
            if 'retire' in r:
                require(g.get('payment_hash')==c['payment_hash'] and g.get('phase')=='expired' and g.get('binding') is None, 'retirement_unconfirmed')
                self.terminal_channel(c, r, pin)
                return
            binding = g.get('binding')
            if routed(c):
                require(r.get('incoming_pin') in incoming_pins(c) and binding == r.get('incoming_binding'),
                        'incoming_binding_changed')
                pin = r['incoming_pin']
            require(g.get('payment_hash') == c['payment_hash'] and g.get('phase') in ('resolved','failed')
                    and type(binding) is list and len(binding) == 2 and type(binding[1]) is int
                    and binding[0] == pin['short_channel_id'], 'previous_gate_not_terminal')
            action, other = ('release','fail') if g['phase'] == 'resolved' else ('fail','release')
            require(r.get(action) == dict(binding=binding) and other not in r, 'previous_resolution_unknown')
        else:
            p = self.rpc('listsendpays', payment_hash=c['payment_hash']).get('payments')
            if 'retire' in r:
                require('send' not in r and p==[], 'retired_outgoing_changed')
                self.terminal_channel(c, r, pin)
                return
            require('send' in r and type(p) is list and len(p) == 1, 'previous_attempt_unknown')
            p = dict(p[0]); p.setdefault('partid', 0)
            require(all(type(p.get(k)) is type(v) and p.get(k) == v for k,v in
                        dict(payment_hash=c['payment_hash'],groupid=1,partid=0,amount_sent_msat=sent_amount(c)).items())
                    and p.get('status') in ('complete','failed'), 'previous_attempt_not_terminal')
            if p['status']=='complete':
                import hashlib
                require(hex32(p.get('payment_preimage')) and hashlib.sha256(bytes.fromhex(p['payment_preimage'])).hexdigest()==c['payment_hash'], 'previous_preimage_invalid')
            else: require(not p.get('payment_preimage'), 'contradictory_previous_outcome')
        self.terminal_channel(c, r, pin, binding)
    def prior(self, except_id=None, cross=True):
        if cross:
            from swap_session import Session as OtherSession
            OtherSession(self.root,self.role,self.rpc,self.clock).prior(cross=False)
        for path in self.records().glob('*.json'):
            if path.stem != except_id: self.terminal(load(path))
        # A reserved slot with no complete record must never be silently skipped.
        for path in self.sessions().glob('*.json'):
            s = load(path)
            for pilot_id in s['enrolled']:
                require((self.records()/(pilot_id+'.json')).exists() or pilot_id == except_id,
                        'enrollment_outcome_unknown')
    def enable(self, channel_id, max_swaps, confirmed, new_grant=False, routed_grant=True, max_delay=80, market_limits=None):
        require(type(max_delay) is int and max_delay in GRANT_LIMITS.values(), 'invalid_route_limit')
        require(routed_grant is True, 'routed_reverse_required')
        require(confirmed is True and type(new_grant) is bool and type(routed_grant) is bool, 'confirmation_required')
        require(type(max_swaps) is int and 1 <= max_swaps <= 10, 'invalid_swap_limit')
        if market_limits is not None:
            mt.limits(market_limits);require(routed_grant is True,'market_grants_required')
            require(max_delay==288,'invalid_route_limit')
        self.node.barrier()
        active = self.root/'reverse-session.json'
        if active.exists() and not new_grant:
            s = self.read(load(active)['session_id'])
            require((not channel_id or s['channel']['short_channel_id'] == channel_id)
                    and s.get('market_limits')==market_limits and s.get('routed',False)==routed_grant and s['max_swaps'] == max_swaps and s.get('rune'), 'existing_grant_differs_or_uncertain')
            return self.grant(s)
        self.prior()
        self.enable_gate()
        info = self.rpc('getinfo')
        require(info.get('network') == self.node.network and not any(k.startswith('warning') for k in info), 'identity_unavailable')
        rows = self.rpc('listpeerchannels').get('channels')
        require(type(rows) is list, 'invalid_channels')
        choices = [r for r in rows if r.get('state') == 'CHANNELD_NORMAL' and r.get('peer_connected') is True
                   and r.get('htlcs') == [] and (not channel_id or r.get('short_channel_id') == channel_id)]
        require((1<=len(choices)<=8) if routed_grant else len(choices)==1, 'choose_one_connected_channel')
        choices.sort(key=lambda r:r['short_channel_id'])
        pin = {k:choices[0][k] for k in FIELDS}
        require(all(type(r.get('short_channel_id')) is str and hex32(r.get('channel_id')) and hex32(r.get('funding_txid'))
                    and type(r.get('funding_outnum')) is int for r in choices),'invalid_channels')
        now = int(self.clock()); session_id = secrets.token_hex(32)
        profile = next(profile for profile, limit in GRANT_LIMITS.items() if limit == max_delay)
        s = dict(schema=1, profile=profile, session_id=session_id, role=self.role, node_id=info['id'], channel=pin,
                 created_at=now, expires_at=now+86400, max_swaps=max_swaps, enrolled={}, paused=False,
                 credential_intent=True, routed=routed_grant, channels=[{k:r[k] for k in FIELDS} for r in choices])
        if market_limits is not None:s.update(market_limits=market_limits,market_reserved={})
        self.write(s); save(active, {'session_id':session_id})
        # Restrict method, named parameter set and this grant ID on the CLN server.
        restrictions = [['method=swap-reverse-call'], ['pnamesession_id='+session_id], ['pnum=5']]
        result = self.rpc('createrune', restrictions=restrictions)
        require(type(result.get('rune')) is str and result.get('unique_id') is not None, 'credential_reply_unknown')
        s.update(rune=result['rune'], unique_id=result['unique_id']); self.write(s)
        self.enable_gate()
        return self.grant(s)
    def enable_gate(self):
        # Existing explicit XBT gate activation remains identity/restore bound.
        if self.role == 'xbt':
            require(RepeatNode.gate_ready(self, self.rpc('reverse-pilot-info')), 'restart_xbt_for_reverse_gate')
    def grant(self, s):
        self.enable_gate()
        return dict(session_id=s['session_id'], credential=json.dumps({'session_id':s['session_id'],'rune':s['rune']},separators=(',',':')),
                    market_limits=s.get('market_limits'),max_swaps=s['max_swaps'], max_delay_blocks=GRANT_LIMITS[s['profile']], expires_at=s['expires_at'], restart_required=False, payment_started=False)
    def pause(self):
        s=self.read(load(self.root/'reverse-session.json')['session_id']);s['paused']=True;self.write(s)
        return dict(paused=True, recovery_preserved=True)
    def enroll(self, s, c):
        validate(c); mt.grant_check(s,c); pilot_id=digest(c)
        # A new binary never widens authority already issued by an older grant.
        require(s.get('profile') in GRANT_LIMITS and route_limit(c) <= GRANT_LIMITS[s['profile']],
                'contract_exceeds_grant_timing')
        node=RepeatNode(self.root,self.role,pilot_id,self.rpc,self.clock)
        if node.path.exists():require('retire' not in load(node.path),'retired_swap')
        require(c['nodes'][self.role] == s['node_id'] and routed(c)==s.get('routed',False), 'outside_session_channel')
        if routed(c):
            require(c['channels'][self.role] in s['channels'] and (self.role!='xbt' or incoming_pins(c)==s['channels']), 'outside_session_channel')
        else: require(c['channels'][self.role]==s['channel'],'outside_session_channel')
        # Idempotence is exact and works after expiry/pause; it never reserves again.
        if pilot_id in s['enrolled']:
            require(s['enrolled'][pilot_id] == c['payment_hash'], 'enrollment_changed')
            if node.path.exists():
                r=node.record(pilot_id);require(r['session_id']==s['session_id'],'enrollment_changed')
                return dict(pilot_id=pilot_id)
        else:
            require(load(self.root/'reverse-session.json')['session_id'] == s['session_id']
                    and not s['paused'] and s['created_at'] <= int(self.clock()) < s['expires_at'], 'session_closed')
            require(len(s['enrolled']) < s['max_swaps'], 'session_limit_reached')
            self.prior()
            require(not node.path.exists(), 'swap_already_enrolled')
            all_records = [load(p) for p in self.records().glob('*.json')]
            all_records += [load(p) for p in folder(self.root,'forward-swaps').glob('*.json')]
            legacy=self.root/'forward-pilot.json'
            if legacy.exists():all_records.append(load(legacy))
            require(not any(r['contract']['payment_hash']==c['payment_hash'] for r in all_records), 'payment_hash_reused')
            now=int(self.clock());require(c['created_at']<=now<c['admission_until'],'admission_expired')
            node.identity(c);ch=node.channel(c)
            require(ch.get('state')=='CHANNELD_NORMAL' and ch.get('peer_connected') is True and ch.get('htlcs')==[], 'channel_not_ready')
            if self.role=='btc':
                node.invoice(c,self.rpc('decode',string=c['invoice']),now+120)
                require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[], 'outgoing_already_exists')
            else: require(node.gate_ready(self.rpc('reverse-pilot-info')), 'restart_xbt_for_repeat_gate')
            mt.reserve(s,c,pilot_id)
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
            return dict(profile=s['profile'],max_delay_blocks=GRANT_LIMITS[s['profile']],session_id=session_id,node_id=s['node_id'],network=self.node.network,channel=s['channel'],routed=s.get('routed',False),channels=s.get('channels',[s['channel']]),
                        market_limits=s.get('market_limits'),market_reserved=s.get('market_reserved',{}),remaining=s['max_swaps']-len(s['enrolled']),expires_at=s['expires_at'],paused=s['paused'],
                        current=load(self.root/'reverse-session.json')['session_id']==session_id,
                        gate_ready=self.role!='xbt' or RepeatNode.gate_ready(self,self.rpc('reverse-pilot-info')))
        if operation=='plan':
            require(self.role=='btc' and s.get('routed') is True and pilot_id==preimage==''
                    and not s['paused'] and int(self.clock())<s['expires_at']
                    and load(self.root/'reverse-session.json')['session_id']==session_id,'route_planning_refused')
            self.prior() # Route discovery must not occupy the plugin during active recovery.
            from reverse_plan import plan
            hops=plan(self.rpc,contract,s['node_id'],max_delay=GRANT_LIMITS[s['profile']],market_limits=s.get('market_limits'))
            pins=[p for p in s['channels'] if p['short_channel_id']==hops[0]['channel'] and p['peer_id']==hops[0]['id']]
            require(len(pins)==1,'route_outside_grant')
            return dict(route=hops,channel=pins[0])
        if operation=='expire':
            require(preimage=='' and len(contract)<=32768,'invalid_parameters')
            c=validate(json.loads(contract));mt.grant_check(s,c)
            require(mt.market(c) and digest(c)==pilot_id and int(self.clock())>=c['pricing']['expires_at'],'retirement_refused')
            require(c['nodes'][self.role]==s['node_id'] and c['channels'][self.role] in s['channels'],'outside_session_channel')
            node=RepeatNode(self.root,self.role,pilot_id,self.rpc,self.clock)
            if node.path.exists():
                r=node.record(pilot_id);require(r['session_id']==session_id,'enrollment_changed')
            else:
                require(pilot_id not in s['enrolled'] or s['enrolled'][pilot_id]==c['payment_hash'],'enrollment_changed')
                r=dict(schema=1,role=self.role,pilot_id=pilot_id,contract=c,session_id=session_id)
            require(not any(k in r for k in ('send','close','release','fail')),'retirement_refused')
            require(self.rpc('listsendpays',payment_hash=c['payment_hash']).get('payments')==[],'outgoing_already_exists')
            if self.role=='xbt' and 'publish' in r:
                g=self.rpc('reverse-status',payment_hash=c['payment_hash'])
                if g.get('binding') is not None or g.get('phase')=='held':return {'accepted':True}
                require(g.get('phase') in ('quoted','expired'),'retirement_refused')
                if 'retire' not in r:node.intent(r,'retire',True)
                if g['phase']!='expired':require(self.rpc('reverse-retire-repeat',payment_hash=c['payment_hash'])=={'retired':True},'retirement_unknown')
            else:
                require('publish' not in r,'wrong_role')
                self.terminal_channel(c,dict(r,retire=True),c['channels'][self.role])
                r.update(retire=True,unpublished_retired=True);save(node.path,r)
            return {'retired':True}
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
            if self.role=='xbt':
                require('publish' in r and r['publish']['terms']['expires_at']<=int(self.clock()),'quote_not_expired')
                g=self.rpc('reverse-status',payment_hash=r['contract']['payment_hash'])
                require(g.get('phase') in ('quoted','expired') and g.get('binding') is None,'quote_was_accepted')
                if 'retire' not in r:node.intent(r,'retire',True)
                if g['phase']!='expired':
                    require(self.rpc('reverse-retire-repeat',payment_hash=r['contract']['payment_hash'])=={'retired':True},'retirement_unknown')
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
            fields={'channel','maxSwaps','confirmed','newGrant','routed'}
            require(set(request)-{'marketLimits'} in (fields, fields|{'maxDelay'}),'invalid_request')
            result=session.enable(request['channel'],request['maxSwaps'],request['confirmed'],request['newGrant'],request['routed'],request.get('maxDelay',80),market_limits=request.get('marketLimits'))
        else:
            require(mode=='pause' and request=={'confirmed':True},'confirmation_required');result=session.pause()
    print(json.dumps(result))


if __name__=='__main__':
    try:main()
    except Exception as error:
        safe={'restored_authority_blocked','choose_one_connected_channel','previous_swap_requires_recovery','previous_gate_not_terminal','previous_attempt_not_terminal','previous_enrollment_unfinished','existing_grant_differs_or_uncertain','invalid_swap_limit'}
        safe.update(mt.ERRORS)
        reason=str(error) if isinstance(error,ValueError) and str(error) in safe else 'session_refused_or_uncertain'
        print(json.dumps(dict(error=reason)));raise SystemExit(1) from None
