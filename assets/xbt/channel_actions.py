#!/usr/bin/env python3
"""Sequential bounded private channels: durable funding/close intent, no mutation retries."""
import fcntl
import hashlib
import ipaddress
import json
import os
from pathlib import Path
import re
import sys
import time

from empty_backup import atomic_json
from recovery import load
from wallet_actions import Wallet, integer, sats, STATE as WITHDRAWAL

STATE = 'channel-pilot.json'


class ChannelValidationError(ValueError):
    pass


def require(condition, message):
    # Only fixed local validation messages may reach the action UI.
    if not condition:
        raise ChannelValidationError(message)


def public_error(error):
    if isinstance(error, ChannelValidationError):
        return str(error)
    return 'Channel action refused or interrupted. Inspect Channel Status and retain the saved attempt. No automatic retry; private details withheld.'


def peer_id(value):
    require(isinstance(value, str) and re.fullmatch(r'0[23][0-9a-f]{64}', value), 'Invalid peer public key')
    return value


def host_name(value):
    require(isinstance(value, str) and 1 <= len(value) <= 253, 'Invalid peer host')
    try:
        ipaddress.ip_address(value)
    except ValueError:
        require(not value.endswith('.onion') and all(re.fullmatch(r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?', label)
                for label in value.split('.')), 'Use an IP address or DNS hostname; Tor is not configured')
    return value


def close_code(state):
    return hashlib.sha256(json.dumps({key: state[key] for key in
        ('node_id', 'peer_id', 'channel_id', 'funding_txid', 'funding_outnum', 'amount_sats')},
        sort_keys=True).encode()).hexdigest()[:16]


class Channels:
    def __init__(self, root, network='xbt', rpc=None):
        self.wallet = Wallet(root, network, rpc)
        self.root, self.network, self.rpc = self.wallet.root, network, self.wallet.rpc

    def connect(self, peer, host, port):
        peer_id(peer); host_name(host); integer(port, 1, 65535)
        require(peer != self.wallet.ready(), 'Cannot connect to self')
        reply = self.rpc('connect', id=peer, host=host, port=port)
        require(reply.get('id') == peer, 'Connected peer identity mismatch')
        peers = self.rpc('listpeers')['peers']
        require(any(p['id'] == peer and p.get('connected') is True for p in peers), 'Peer not connected')
        return {'peer_connected': True, 'channel_funding_attempted': False}

    def record(self):
        state = load(self.root, STATE)
        require(state.get('schema') == 1 and state['node_id'] == self.wallet.ready()
                and state['network'] == self.network, 'Channel pilot identity changed')
        peer_id(state['peer_id'])
        integer(state['amount_sats'], 20000, 80000)
        return state

    def validate_channel(self, state, channel):
        require(channel['peer_id'] == state['peer_id'] and channel.get('private') is True
                and channel.get('opener') == 'local' and channel.get('total_msat') == state['amount_sats'] * 1000,
                'Channel does not match funding intent')
        cid, txid, outnum = channel['channel_id'], channel['funding_txid'], channel['funding_outnum']
        require(re.fullmatch(r'[0-9a-f]{64}', cid) and re.fullmatch(r'[0-9a-f]{64}', txid)
                and type(outnum) is int and outnum >= 0, 'Invalid channel funding identity')
        for key, value in (('channel_id', cid), ('funding_txid', txid), ('funding_outnum', outnum)):
            require(key not in state or state[key] == value, 'Pinned funding identity changed')
        txs = [t for t in self.rpc('listtransactions')['transactions'] if t['hash'] == txid]
        require(len(txs) == 1, 'Funding transaction not yet available for reconciliation')
        actual = {(i['txid'], i['index']) for i in txs[0]['inputs']}
        expected = {(o['txid'], o['output']) for o in state['inputs']}
        require(actual == expected and len(actual) == len(txs[0]['inputs']), 'Funding inputs do not match intent')
        funding = [o for o in txs[0]['outputs'] if o['index'] == outnum]
        require(len(funding) == 1 and funding[0]['amount_msat'] == state['amount_sats'] * 1000,
                'Funding amount does not match intent')
        return {'channel_id': cid, 'funding_txid': txid, 'funding_outnum': outnum}

    def archive_name(self, state):
        cid = state.get('channel_id', '')
        require(re.fullmatch('[0-9a-f]{64}', cid), 'Invalid archived channel identity')
        return 'channel-history-' + cid + '.json'

    def confirmed_close(self, state):
        require(state['node_id'] == self.wallet.ready() and state['network'] == self.network,
                'Archived channel wallet identity changed')
        require(state.get('phase') == 'close-confirmed' and state.get('close_txid'),
                'Only a recorded confirmed cooperative close can be archived')
        txs = [t for t in self.rpc('listtransactions')['transactions'] if t['hash'] == state['close_txid']]
        require(len(txs) == 1 and txs[0]['blockheight'] > 0, 'Cooperative close is not currently confirmed')
        require(any(i['txid'] == state['funding_txid'] and i['index'] == state['funding_outnum']
                    for i in txs[0].get('inputs', [])), 'Close does not spend the pinned channel funding output')

    def history(self):
        records = {}
        for path in sorted(self.root.glob('channel-history-*.json')):
            state = load(self.root, path.name)
            require(path.name == self.archive_name(state), 'Archive filename does not match channel')
            self.confirmed_close(state)
            records[state['channel_id']] = state
        return records

    def only_archived_channels(self, records):
        for c in self.rpc('listpeerchannels')['channels']:
            old = records.get(c.get('channel_id'))
            require(old is not None, 'An unarchived channel still exists')
            require(c['state'] in ('ONCHAIN', 'CLOSINGD_COMPLETE') and not c.get('htlcs'),
                    'Historical channel remains active or has pending HTLCs')
            self.validate_channel(old, c)
        for c in self.rpc('listclosedchannels')['closedchannels']:
            old = records.get(c.get('channel_id'))
            require(old is not None and c.get('funding_txid') == old['funding_txid']
                    and c.get('funding_outnum') == old['funding_outnum'],
                    'Unrecognized historical channel; inspect locally')

    def archive(self, review_code, confirmed):
        require(confirmed is True, 'Archive confirmation required')
        self.status()
        state = self.record()
        require(review_code == close_code(state), 'Close review code does not match')
        name = self.archive_name(state)
        if state['phase'] == 'archived':
            old = load(self.root, name)
            require({**old, 'phase': 'archived'} == state, 'Archived record changed')
            self.confirmed_close(old)
            return self.status()
        self.confirmed_close(state)
        records = self.history()
        records[state['channel_id']] = state
        self.only_archived_channels(records)
        outputs = self.rpc('listfunds')['outputs']
        require(any(o['txid'] == state['close_txid'] and o['status'] == 'confirmed'
                    and o['reserved'] is False for o in outputs),
                'Wait for confirmed unreserved wallet funds from this close')
        if os.path.lexists(self.root / name):
            require(load(self.root, name) == state, 'Existing archive differs; nothing overwritten')
        else:
            atomic_json(self.root, name, state)
        # Copy is durable first; a crash here can resume without losing the original.
        atomic_json(self.root, STATE, {**state, 'phase': 'archived'})
        return self.status()

    def status(self):
        self.wallet.ready()
        channels = self.rpc('listpeerchannels')['channels']
        if not os.path.lexists(self.root / STATE):
            return {'phase': 'not-started', 'listed_channels': len(channels), 'automatic_retry': False}
        state = self.record()
        if state['phase'] == 'archived':
            old = load(self.root, self.archive_name(state))
            require({**old, 'phase': 'archived'} == state, 'Archived record changed')
            self.confirmed_close(old)
            return {'phase': 'archived', 'next_channel_code': close_code(state),
                    'automatic_retry': False, 'channel_funding_attempted': False}
        matches = [c for c in channels if c['peer_id'] == state['peer_id']]
        if 'channel_id' in state:
            matches = [c for c in matches if c.get('channel_id') == state['channel_id']]
        else:
            archived_ids = set(self.history())
            matches = [c for c in matches if c.get('channel_id') not in archived_ids]
        require(len(matches) <= 1, 'Ambiguous pilot channel; inspect locally')
        if matches and all(k in matches[0] for k in ('channel_id', 'funding_txid', 'funding_outnum')):
            state.update(self.validate_channel(state, matches[0]))
            atomic_json(self.root, STATE, state)
        if state.get('close_txid'):
            txs = self.rpc('listtransactions')['transactions']
            if any(t['hash'] == state['close_txid'] and t['blockheight'] > 0 for t in txs):
                state['phase'] = 'close-confirmed'
                atomic_json(self.root, STATE, state)
        result = {'phase': state['phase'], 'channel_sats': state['amount_sats'], 'automatic_retry': False,
                  'funding_pin_saved': 'channel_id' in state,
                  'channel_state': matches[0]['state'] if matches else 'not-listed'}
        if matches:
            c = matches[0]
            result.update(peer_connected=c.get('peer_connected', False), private=c.get('private'),
                          pending_htlcs=len(c.get('htlcs', [])),
                          local_balance_sats=sats(c['to_us_msat']) if 'to_us_msat' in c and c['to_us_msat'] % 1000 == 0 else None)
        if 'channel_id' in state:
            result['close_review_code'] = close_code(state)
        if state['phase'] == 'funding-submitted' and not state.get('channel_id'):
            result['inspection_required'] = True
        return result

    def open(self, peer, amount_sats, fee_rate, confirmed, previous_close_code=""):
        require(confirmed is True, 'Funding confirmation required')
        peer_id(peer); integer(amount_sats, 20000, 80000); integer(fee_rate, 2, 10)
        node = self.wallet.ready()
        require(node != peer, 'Cannot fund a channel to self')
        if os.path.lexists(self.root / STATE):
            state = self.record()
            if state['phase'] != 'archived':
                require((state['peer_id'], state['amount_sats'], state['fee_rate'], state.get('previous_close_code', ''))
                        == (peer, amount_sats, fee_rate, previous_close_code),
                        'An existing pilot funding attempt differs; inspect Channel Status')
                return self.status()  # No repeat can originate funding again.
            self.status()
            require(previous_close_code == close_code(state), 'Copy the next channel code from the archived Channel Status')
        else:
            require(previous_close_code == '', 'No previous archived channel exists')
        if os.path.lexists(self.root / WITHDRAWAL):
            require(self.wallet.status()['phase'] in ('confirmed', 'cancelled'), 'Resolve the prior withdrawal first')
        self.only_archived_channels(self.history())
        require(any(p['id'] == peer and p.get('connected') is True for p in self.rpc('listpeers')['peers']),
                'Connect the selected peer first')
        outputs = self.rpc('listfunds')['outputs']
        require(1 <= len(outputs) <= 10 and all(o['status'] == 'confirmed' and o['reserved'] is False for o in outputs),
                'Need confirmed unreserved wallet outputs only')
        total = sum(sats(o['amount_msat']) for o in outputs)
        require(amount_sats + 10000 <= total, 'Keep at least 10,000 confirmed unreserved sats above the channel amount')
        state = {'schema': 1, 'network': self.network, 'node_id': node, 'peer_id': peer,
                 'amount_sats': amount_sats, 'fee_rate': fee_rate, 'inputs': outputs,
                 'phase': 'funding-submitted', 'created_at': int(time.time()),
                 'previous_close_code': previous_close_code}
        atomic_json(self.root, STATE, state)
        reply = self.rpc('fundchannel', id=peer, amount=f'{amount_sats}sat', feerate=f'{fee_rate*1000}perkb',
                         announce=False, minconf=1, mindepth=3, push_msat=0,
                         utxos=[o['txid'] + ':' + str(o['output']) for o in outputs])
        state.update(channel_id=reply['channel_id'], funding_txid=reply['txid'], funding_outnum=reply['outnum'])
        atomic_json(self.root, STATE, state)
        return self.status()

    def close(self, review_code, confirmed):
        require(confirmed is True, 'Cooperative close confirmation required')
        self.status()  # Reconcile and validate before accepting a close target.
        state = self.record()
        require('channel_id' in state and review_code == close_code(state), 'Close review code does not match')
        if state['phase'] in ('close-requested', 'close-confirmed'):
            return self.status()
        require(state['phase'] == 'funding-submitted', 'Unexpected pilot phase')
        channels = self.rpc('listpeerchannels')['channels']
        matches = [c for c in channels if c.get('channel_id') == state['channel_id']]
        require(len(matches) == 1, 'Pinned channel not found')
        c = matches[0]
        self.validate_channel(state, c)
        require(c['state'] == 'CHANNELD_NORMAL' and c.get('peer_connected') is True and not c.get('htlcs'),
                'Close requires a connected normal channel with no pending HTLCs')
        state['phase'] = 'close-requested'
        atomic_json(self.root, STATE, state)
        reply = self.rpc('close', id=state['channel_id'], unilateraltimeout=0,
                         feerange=[f"{state['fee_rate']*1000}perkb", f"{state['fee_rate']*1000}perkb"])
        txids = reply.get('txids', [])
        require(reply.get('type') == 'mutual' and isinstance(txids, list) and len(txids) == 1
                and re.fullmatch(r'[0-9a-f]{64}', txids[0]), 'Inspect close outcome locally')
        state['close_txid'] = txids[0]
        atomic_json(self.root, STATE, state)
        return self.status()

    def execute(self, operation, **params):
        # Shared with wallet actions, so funding cannot race withdrawal preparation.
        with (self.root / 'wallet-pilot.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(operation in ('connect', 'status', 'open', 'close', 'archive'), 'Unknown channel action')
            return getattr(self, operation)(**params)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        request = json.loads(sys.stdin.read(4096))
        root = Path(sys.argv[1]).resolve(strict=True)
        print(json.dumps(Channels(root).execute(**request)))
    except Exception as error:
        print(json.dumps({'error': public_error(error)}))
        sys.exit(1)
