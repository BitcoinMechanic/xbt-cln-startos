import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
import wallet_actions as w

ADDRESS = 'bcrt1qsxdxcrmq7rqp2e2l690k0rgc722yzkv49exkx2uwkkk6yevxlygq3lv4xs'
SCRIPT = bytes.fromhex('0020819a6c0f60f0c015655fd15f678d18f2944159952e4d632b8eb5ada26586f910')
NODE = '02' + '12' * 32


def rawtx(amount=9700, script=SCRIPT):
    return (struct.pack('<I', 2) + b'\x01' + bytes.fromhex('34'*32) + struct.pack('<I', 0)
            + b'\x00\xfd\xff\xff\xff\x01' + struct.pack('<Q', amount)
            + bytes([len(script)]) + script + bytes(4)).hex()


class WalletTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.calls = []
        self.info = {'network': 'xbt-regtest', 'id': NODE}
        self.outputs = [{'txid': '34'*32, 'output': 0, 'amount_msat': 10000000,
                         'scriptpubkey': SCRIPT.hex(), 'status': 'confirmed', 'reserved': False}]
        self.channels, self.transactions = [], []
        self.lost, self.change = None, None
        self.wallet = w.Wallet(self.root, 'xbt-regtest', self.rpc)

    def rpc(self, method, **params):
        self.calls.append((method, params))
        if method == 'getinfo': return self.info
        if method == 'listfunds': return {'outputs': copy.deepcopy(self.outputs)}
        if method == 'listpeerchannels': return {'channels': self.channels}
        if method == 'listtransactions': return {'transactions': self.transactions}
        if method == 'newaddr': return {'bech32': ADDRESS}
        if method == 'txprepare':
            self.assertEqual(params['minconf'], 1)
            self.assertEqual(params['feerate'], '2000perkb')
            self.assertEqual(params['utxos'], ['34'*32 + ':0'])
            self.assertEqual(params['outputs'], [{ADDRESS: 'all'}])
            self.outputs[0]['reserved'] = True
            reply = {'unsigned_tx': rawtx(), 'txid': w.unsigned_transaction(rawtx())[0]}
            if self.change: reply.update(self.change)
        elif method in ('txsend', 'txdiscard'):
            reply = {'txid': params['txid']}
        else: raise AssertionError(method)
        if self.lost == method: raise RuntimeError('simulated lost reply')
        return reply

    def prepare(self, **overrides):
        params = {'destination': ADDRESS, 'fee_rate': 2, 'max_fee_sats': 2000, **overrides}
        return self.wallet.execute('prepare', **params)

    def methods(self, name):
        return sum(m == name for m, _ in self.calls)

    def test_address_reused_and_funds_private(self):
        self.assertEqual(self.wallet.execute('address')['address'], ADDRESS)
        self.wallet.execute('address')
        self.assertEqual(self.methods('newaddr'), 1)
        result = self.wallet.execute('funds')
        self.assertEqual(result['confirmed_unreserved_sats'], 10000)
        self.assertNotIn('34'*32, json.dumps(result))

    def test_prepare_review_send_confirm_and_no_resend(self):
        result = self.prepare()
        self.assertEqual((result['amount_sats'], result['fee_sats']), (9700, 300))
        self.assertEqual(self.methods('txsend'), 0)
        self.prepare()
        self.assertEqual(self.methods('txprepare'), 1)
        with self.assertRaises(ValueError): self.wallet.execute('send', review_code='wrong')
        result = self.wallet.execute('send', review_code=result['review_code'])
        self.assertEqual(result['phase'], 'broadcast')
        self.transactions = [{'hash': w.unsigned_transaction(rawtx())[0], 'blockheight': 200}]
        self.assertEqual(self.wallet.execute('status')['phase'], 'confirmed')
        self.wallet.execute('send', review_code=result['review_code'])
        self.assertEqual(self.methods('txsend'), 1)

    def test_lost_submission_never_resends_and_unconfirmed_record_is_not_proof(self):
        result = self.prepare()
        self.lost = 'txsend'
        with self.assertRaises(RuntimeError): self.wallet.execute('send', review_code=result['review_code'])
        self.transactions = [{'hash': w.unsigned_transaction(rawtx())[0], 'blockheight': 0}]
        self.assertEqual(self.wallet.execute('send', review_code=result['review_code'])['phase'], 'submitting')
        self.assertEqual(self.methods('txsend'), 1)
        self.transactions[0]['blockheight'] = 200
        self.assertEqual(self.wallet.execute('status')['phase'], 'confirmed')

    def test_lost_preparation_is_durable_and_never_reprepared(self):
        self.lost = 'txprepare'
        with self.assertRaises(RuntimeError): self.prepare()
        fresh = w.Wallet(self.root, 'xbt-regtest', self.rpc)
        self.assertEqual(fresh.execute('status')['phase'], 'preparing')
        self.assertEqual(self.prepare()['phase'], 'preparing')
        self.assertEqual(self.methods('txprepare'), 1)

    def test_cancel_exact_once_and_cannot_send_after_cancel(self):
        result = self.prepare()
        for _ in range(2):
            self.assertEqual(self.wallet.execute('cancel', review_code=result['review_code'])['phase'], 'cancelled')
        self.assertEqual(self.methods('txdiscard'), 1)
        with self.assertRaises(ValueError): self.wallet.execute('send', review_code=result['review_code'])
        self.assertEqual(self.methods('txsend'), 0)

    def test_lost_cancel_stays_uncertain(self):
        result = self.prepare()
        self.lost = 'txdiscard'
        with self.assertRaises(RuntimeError): self.wallet.execute('cancel', review_code=result['review_code'])
        with self.assertRaises(ValueError): self.wallet.execute('cancel', review_code=result['review_code'])
        self.assertEqual(self.wallet.execute('status')['phase'], 'cancelling')
        self.assertEqual(self.methods('txdiscard'), 1)

    def test_wrong_identity_warning_recovery_block_mutations(self):
        for field, value in [('network', 'bitcoin'), ('warning_lightningd_sync', 'syncing'), ('id', 'wrong')]:
            old = self.info.copy(); self.info[field] = value
            with self.assertRaises(ValueError): self.prepare()
            self.info = old
        w.atomic_json(self.root, 'recovery-intent.json', {'schema': 1, 'network': 'xbt-regtest', 'node_id': NODE,
                                                     'channels': [], 'phase': 'imported'})
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.methods('txprepare'), 0)

    def test_balance_channels_unconfirmed_reserved_limits(self):
        for change in ({'amount_msat': 100001000}, {'status': 'unconfirmed'}, {'status': 'immature'}, {'reserved': True}):
            old = self.outputs[0].copy(); self.outputs[0].update(change)
            with self.assertRaises(ValueError): self.prepare()
            self.outputs[0] = old
        self.channels = [{'state': 'ONCHAIN'}]
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.methods('txprepare'), 0)

    def test_invalid_inputs_refused_before_preparation(self):
        for values in ({'fee_rate': 1}, {'fee_rate': True}, {'max_fee_sats': 10001}, {'destination': ADDRESS[:-1]+'q'}):
            with self.assertRaises(ValueError): self.prepare(**values)
        self.assertEqual(self.methods('txprepare'), 0)

    def test_changed_transaction_never_send(self):
        self.change = {'txid': '56'*32}
        with self.assertRaises(ValueError): self.prepare()
        self.assertEqual(self.wallet.execute('status')['phase'], 'needs-review')
        self.assertEqual(self.methods('txsend'), 0)

    def test_fee_cap_saved_refusal_and_no_broadcast(self):
        with self.assertRaises(ValueError): self.prepare(max_fee_sats=200)
        self.assertEqual(self.wallet.execute('status')['phase'], 'needs-review')
        self.assertEqual(self.methods('txsend'), 0)

    def test_changed_review_or_current_inputs_never_send(self):
        result = self.prepare()
        self.outputs[0]['reserved'] = False
        with self.assertRaises(ValueError): self.wallet.execute('send', review_code=result['review_code'])
        self.outputs[0]['reserved'] = True
        state = w.load(self.root, w.STATE); state['amount_sats'] += 1
        w.atomic_json(self.root, w.STATE, state)
        with self.assertRaises(ValueError): self.wallet.execute('send', review_code=result['review_code'])
        self.assertEqual(self.methods('txsend'), 0)

    def test_competing_request_is_blocked(self):
        with (self.root / 'wallet-pilot.lock').open('a') as lock:
            w.fcntl.flock(lock, w.fcntl.LOCK_EX | w.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.prepare()
        self.assertEqual(self.calls, [])

    def test_address_and_transaction_vectors(self):
        self.assertEqual(w.script_for(ADDRESS, 'xbt-regtest'), SCRIPT)
        self.assertEqual(w.script_for('bc1p5cyxnuxmeuwuvkwfem96lqzszd02n6xdcjrs20cac6yqjjwudpxqkedrcr', 'xbt').hex(),
                         '5120a60869f0dbcf1dc659c9cecbaf8050135ea9e8cdc487053f1dc6880949dc684c')
        with self.assertRaises(ValueError): w.script_for(ADDRESS, 'xbt')
        for raw in (rawtx()[:-2], rawtx()+'00', '00'*10):
            with self.assertRaises(ValueError): w.unsigned_transaction(raw)


if __name__ == '__main__': unittest.main()
