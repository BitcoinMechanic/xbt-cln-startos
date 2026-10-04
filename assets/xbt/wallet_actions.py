#!/usr/bin/env python3
"""Bounded, single-withdrawal on-chain pilot. No automatic mutation retries."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

from empty_backup import atomic_json, regular
from recovery import load, validate

STATE = 'wallet-pilot-withdrawal.json'
CAP = 100000


def require(ok, message):
    if not ok:
        raise ValueError(message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'Numeric value outside pilot bounds')
    return value


def sats(msat):
    integer(msat, 0, 2100000000000000000)
    require(msat % 1000 == 0, 'Non-integral satoshi amount')
    return msat // 1000


def script_for(address, network):
    """Native segwit v0/v1 only; BIP173/BIP350 checksum and padding validation."""
    require(isinstance(address, str) and address == address.lower() and 14 <= len(address) <= 90,
            'Use a lowercase native SegWit address')
    hrp, sep, tail = address.rpartition('1')
    require(sep and hrp == ('bc' if network == 'xbt' else 'bcrt'), 'Wrong address network')
    alphabet = 'qpzry9x8gf2tvdw0s3jn54khce6mua7l'
    require(len(tail) >= 7 and all(c in alphabet for c in tail), 'Invalid address')
    data = [alphabet.index(c) for c in tail]
    chk = 1
    for value in [ord(c) >> 5 for c in hrp] + [0] + [ord(c) & 31 for c in hrp] + data:
        top = chk >> 25
        chk = (chk & 0x1ffffff) << 5 ^ value
        for i, generator in enumerate((0x3b6a57b2, 0x26508e6d, 0x1ea119fa, 0x3d4233dd, 0x2a1462b3)):
            if top >> i & 1:
                chk ^= generator
    version = data[0]
    require(version in (0, 1) and chk == (1 if version == 0 else 0x2bc830a3), 'Invalid address checksum')
    acc = bits = 0
    program = bytearray()
    for value in data[1:-6]:
        acc = ((acc << 5) | value) & 4095
        bits += 5
        if bits >= 8:
            bits -= 8
            program.append((acc >> bits) & 255)
    require(bits < 5 and (acc << (8 - bits)) & 255 == 0, 'Invalid address padding')
    require(len(program) in ((20, 32) if version == 0 else (32,)), 'Unsupported witness program')
    return bytes([0 if version == 0 else 0x51, len(program)]) + program


def unsigned_transaction(raw):
    require(isinstance(raw, str) and len(raw) <= 20000, 'Invalid transaction size')
    data = bytes.fromhex(raw)
    pos = 0

    def take(n):
        nonlocal pos
        require(pos + n <= len(data), 'Truncated transaction')
        value = data[pos:pos+n]
        pos += n
        return value

    def count():
        n = take(1)[0]
        require(n < 253, 'Oversized or unsupported transaction field')
        return n

    require(int.from_bytes(take(4), 'little') in (1, 2), 'Unsupported transaction version')
    inputs = []
    n = count()
    require(1 <= n <= 10, 'Pilot requires one to ten inputs')
    for _ in range(n):
        txid = take(32)[::-1].hex()
        vout = int.from_bytes(take(4), 'little')
        require(count() == 0, 'Expected unsigned native SegWit input')
        take(4)
        inputs.append((txid, vout))
    require(len(set(inputs)) == len(inputs), 'Duplicate inputs')
    require(count() == 1, 'Pilot withdrawal must have exactly one output')
    amount = int.from_bytes(take(8), 'little')
    script = take(count())
    take(4)
    require(pos == len(data), 'Unexpected trailing transaction bytes')
    txid = hashlib.sha256(hashlib.sha256(data).digest()).digest()[::-1].hex()
    return txid, inputs, amount, script


class Wallet:
    def __init__(self, root, network='xbt', rpc=None):
        require(network in ('xbt', 'xbt-regtest'), 'Wrong wallet network')
        self.root, self.network = Path(root), network
        self.rpc = rpc or self.call

    def call(self, method, **params):
        args = ['lightning-cli', f'--lightning-dir={self.root}', f'--network={self.network}',
                '--json', '--notifications=none', '-k', method]
        args += [key + '=' + json.dumps(value, separators=(',', ':')) for key, value in params.items()]
        result = subprocess.run(args, text=True, capture_output=True, timeout=60)
        require(result.returncode == 0, 'RPC failed; retain the withdrawal record and inspect status before retrying')
        result = json.loads(result.stdout)
        require('error' not in result, 'RPC returned an error')
        return result

    def ready(self):
        require(not any(os.path.lexists(self.root / p) for p in ('restore-blocked', 'bitcoin')),
                'Blocked restore or foreign wallet')
        info = self.rpc('getinfo')
        require(info.get('network') == self.network and re.fullmatch(r'0[23][0-9a-f]{64}', info.get('id', '')),
                'Unexpected wallet identity')
        require(not any(k.startswith('warning_') for k in info), 'Wait for node synchronization')
        if os.path.lexists(self.root / 'restored-identity.json'):
            require(load(self.root, 'restored-identity.json')['node_id'] == info['id'], 'Restored identity mismatch')
        if os.path.lexists(self.root / 'recovery-intent.json'):
            intent = validate(load(self.root, 'recovery-intent.json'), self.network)
            require(intent.get('phase') == 'finished-empty' and intent['channels'] == []
                    and intent.get('completion_scope') == 'operator-confirmed-never-funded'
                    and intent['node_id'] == info['id'], 'Complete empty-wallet recovery first')
        return info['id']

    def address(self):
        self.ready()
        # CLN persists the address index; leave legacy address records untouched.
        reply = self.rpc('newaddr', addresstype='bech32')
        address = reply['bech32']
        script_for(address, self.network)
        return {'address': address, 'network': self.network}

    def funds(self):
        self.ready()
        outputs = self.rpc('listfunds')['outputs']
        return {'confirmed_unreserved_sats': sum(sats(o['amount_msat']) for o in outputs
                    if o['status'] == 'confirmed' and o['reserved'] is False),
                'reserved_outputs': sum(o['reserved'] is True for o in outputs),
                'unconfirmed_or_immature_outputs': sum(o['status'] in ('unconfirmed', 'immature') for o in outputs)}

    def record(self):
        state = load(self.root, STATE)
        require(state['node_id'] == self.ready() and state['network'] == self.network, 'Withdrawal identity changed')
        return state

    def inspect(self, state):
        txid, inputs, amount, script = unsigned_transaction(state['unsigned_tx'])
        require(txid == state['txid'] and script == script_for(state['destination'], self.network), 'Prepared transaction changed')
        coins = {(o['txid'], o['output']): sats(o['amount_msat']) for o in state['inputs']}
        require(len(coins) == len(state['inputs']) and set(inputs) == set(coins), 'Prepared input binding changed')
        total = sum(coins.values())
        fee = total - amount
        require(546 <= amount < total <= CAP and 0 < fee <= state['max_fee_sats'] <= 10000,
                'Prepared amount or fee exceeds pilot bounds')
        require(state['amount_sats'] == amount and state['fee_sats'] == fee, 'Review amounts changed')
        code = hashlib.sha256((state['node_id'] + txid + state['destination']).encode()).hexdigest()[:16]
        require(state['review_code'] == code, 'Review binding changed')
        return {'phase': state['phase'], 'destination': state['destination'], 'amount_sats': amount,
                'fee_sats': fee, 'fee_rate_sat_vbyte': state['fee_rate'], 'review_code': code}

    def prepare(self, destination, fee_rate, max_fee_sats):
        node = self.ready()
        script_for(destination, self.network)
        integer(fee_rate, 2, 100)
        integer(max_fee_sats, 1, 10000)
        if os.path.lexists(self.root / STATE):
            state = self.record()
            require((state['destination'], state['fee_rate'], state['max_fee_sats']) ==
                    (destination, fee_rate, max_fee_sats), 'Existing withdrawal differs; use Withdrawal Status')
            return self.status()  # Never prepare twice, even after an ambiguous reply.
        require(not os.path.lexists(self.root / 'channel-pilot.json'), 'Channel pilot exists; do not prepare a separate pilot withdrawal')
        require(self.rpc('listpeerchannels')['channels'] == [], 'This pilot requires a wallet with no channels')
        outputs = self.rpc('listfunds')['outputs']
        require(1 <= len(outputs) <= 10 and all(o['status'] == 'confirmed' and o['reserved'] is False for o in outputs),
                'Need one to ten confirmed, unreserved outputs and no other wallet outputs')
        require(0 < sum(sats(o['amount_msat']) for o in outputs) <= CAP, 'On-chain balance exceeds 100,000-sat pilot cap')
        require(all(re.fullmatch(r'(0014[0-9a-f]{40}|0020[0-9a-f]{64}|5120[0-9a-f]{64})', o['scriptpubkey']) for o in outputs),
                'Pilot requires native SegWit inputs')
        state = {'schema': 1, 'network': self.network, 'node_id': node, 'phase': 'preparing',
                 'destination': destination, 'fee_rate': fee_rate, 'max_fee_sats': max_fee_sats,
                 'inputs': outputs, 'created_at': int(time.time())}
        atomic_json(self.root, STATE, state)
        reply = self.rpc('txprepare', outputs=[{destination: 'all'}], feerate=f'{fee_rate * 1000}perkb',
                         minconf=1, utxos=[o['txid'] + ':' + str(o['output']) for o in outputs])
        # Save the exact returned transaction even if validation subsequently refuses it.
        state.update(phase='needs-review', txid=reply['txid'], unsigned_tx=reply['unsigned_tx'])
        atomic_json(self.root, STATE, state)
        _, _, amount, _ = unsigned_transaction(state['unsigned_tx'])
        state.update(amount_sats=amount, fee_sats=sum(sats(o['amount_msat']) for o in outputs)-amount,
                     review_code=hashlib.sha256((node + state['txid'] + destination).encode()).hexdigest()[:16])
        self.inspect(state)
        state['phase'] = 'prepared'
        atomic_json(self.root, STATE, state)
        return self.inspect(state)

    def status(self):
        self.ready()
        if not os.path.lexists(self.root / STATE):
            return {'phase': 'not-prepared'}
        state = self.record()
        if state['phase'] in ('submitting', 'broadcast', 'confirmed'):
            matches = [t for t in self.rpc('listtransactions')['transactions'] if t['hash'] == state['txid']]
            # A tracked transaction alone is not proof of broadcast: require a mined block.
            if matches and matches[0]['blockheight'] > 0:
                state['phase'] = 'confirmed'
                atomic_json(self.root, STATE, state)
        if state['phase'] in ('preparing', 'needs-review', 'cancelling'):
            return {'phase': state['phase'], 'inspection_required': True, 'automatic_retry': False}
        return {**self.inspect(state), 'automatic_retry': False}

    def send(self, review_code):
        state = self.record()
        summary = self.inspect(state)
        require(review_code == summary['review_code'], 'Review code does not match')
        if state['phase'] in ('submitting', 'broadcast', 'confirmed'):
            return self.status()
        require(state['phase'] == 'prepared', 'Withdrawal is not ready to send')
        require(self.rpc('listpeerchannels')['channels'] == [], 'Channel state changed')
        current = {(o['txid'], o['output']): o for o in self.rpc('listfunds')['outputs']}
        for o in state['inputs']:
            c = current.get((o['txid'], o['output']))
            require(c and c['status'] == 'confirmed' and c['reserved'] is True
                    and c['amount_msat'] == o['amount_msat'] and c['scriptpubkey'] == o['scriptpubkey'],
                    'Prepared inputs changed or lost their reservation')
        state['phase'] = 'submitting'
        atomic_json(self.root, STATE, state)
        reply = self.rpc('txsend', txid=state['txid'])
        require(reply.get('txid') == state['txid'], 'Unexpected submission result')
        state['phase'] = 'broadcast'
        atomic_json(self.root, STATE, state)
        return self.status()

    def cancel(self, review_code):
        state = self.record()
        summary = self.inspect(state)
        require(review_code == summary['review_code'], 'Review code does not match')
        if state['phase'] == 'cancelled':
            return self.status()
        require(state['phase'] == 'prepared', 'Cannot cancel a submitted or uncertain withdrawal')
        state['phase'] = 'cancelling'
        atomic_json(self.root, STATE, state)
        reply = self.rpc('txdiscard', txid=state['txid'])
        require(reply.get('txid') == state['txid'], 'Unexpected cancellation result')
        state['phase'] = 'cancelled'
        atomic_json(self.root, STATE, state)
        return self.status()

    def execute(self, operation, **params):
        # Serializes UI requests; durable phases prevent retry after the process exits.
        with (self.root / 'wallet-pilot.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            require(operation in ('address', 'funds', 'prepare', 'status', 'send', 'cancel'), 'Unknown action')
            return getattr(self, operation)(**params)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        request = json.loads(sys.stdin.read(4096))
        root = Path(sys.argv[1]).resolve(strict=True)
        print(json.dumps(Wallet(root).execute(**request)))
    except Exception:
        print(json.dumps({'error': 'Wallet action refused or interrupted. Use Withdrawal Status; do not delete the record or retry through another wallet command. Private details withheld.'}))
        sys.exit(1)
