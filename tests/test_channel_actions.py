import copy
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
import channel_actions as c
from wallet_actions import Wallet

NODE, PEER = '02'+'11'*32, '03'+'22'*32
CID, FUNDING, CLOSE, DEPOSIT = '33'*32, '44'*32, '55'*32, '66'*32


class ChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.info = {'network': 'xbt-regtest', 'id': NODE}
        self.channels, self.txs, self.closed, self.calls = [], [], [], []
        self.peers = [{'id': PEER, 'connected': True}]
        self.outputs = [{'txid': DEPOSIT, 'output': 0, 'amount_msat': 80000000,
                         'status': 'confirmed', 'reserved': False, 'scriptpubkey': '0014'+'00'*20}]
        self.lost = None
        self.helper = c.Channels(self.root, 'xbt-regtest', self.rpc)

    def rpc(self, method, **params):
        self.calls.append((method, params))
        if method == 'getinfo': return self.info
        if method == 'listpeers': return {'peers': self.peers}
        if method == 'listpeerchannels': return {'channels': copy.deepcopy(self.channels)}
        if method == 'listclosedchannels': return {'closedchannels': self.closed}
        if method == 'listtransactions': return {'transactions': copy.deepcopy(self.txs)}
        if method == 'listfunds': return {'outputs': copy.deepcopy(self.outputs)}
        if method == 'connect': return {'id': PEER}
        if method == 'fundchannel':
            self.assertEqual(c.load(self.root, c.STATE)['phase'], 'funding-submitted')
            self.assertEqual(params['id'], PEER)
            self.assertEqual(params['amount'], '50000sat')
            self.assertEqual(params['feerate'], '2000perkb')
            self.assertEqual(params['announce'], False)
            self.assertEqual(params['push_msat'], 0)
            self.assertEqual(params['minconf'], 1)
            self.assertEqual(params['utxos'], [DEPOSIT+':0'])
            self.channels = [{'peer_id': PEER, 'channel_id': CID, 'funding_txid': FUNDING,
                'funding_outnum': 0, 'total_msat': 50000000, 'private': True, 'opener': 'local',
                'state': 'CHANNELD_NORMAL', 'peer_connected': True, 'htlcs': [], 'to_us_msat': 50000000}]
            self.txs = [{'hash': FUNDING, 'blockheight': 101,
                'inputs': [{'txid': DEPOSIT, 'index': 0}], 'outputs': [{'index': 0, 'amount_msat': 50000000}]}]
            reply = {'channel_id': CID, 'txid': FUNDING, 'outnum': 0}
        elif method == 'close':
            self.assertEqual(c.load(self.root, c.STATE)['phase'], 'close-requested')
            self.assertEqual(params['id'], CID)
            self.assertEqual(params['unilateraltimeout'], 0)
            self.assertEqual(params['feerange'], ['2000perkb', '2000perkb'])
            self.channels[0]['state'] = 'CLOSINGD_COMPLETE'
            self.txs.append({'hash': CLOSE, 'blockheight': 0})
            reply = {'type': 'mutual', 'txids': [CLOSE]}
        else: raise AssertionError(method)
        if self.lost == method: raise RuntimeError('simulated lost reply')
        return reply

    def open(self, **changes):
        return self.helper.execute('open', **{'peer': PEER, 'amount_sats': 50000,
                                              'fee_rate': 2, 'confirmed': True, **changes})

    def count(self, method): return sum(m == method for m, _ in self.calls)

    def test_connect_only_and_input_validation(self):
        result = self.helper.execute('connect', peer=PEER, host='127.0.0.1', port=19735)
        self.assertTrue(result['peer_connected'])
        self.assertFalse(result['channel_funding_attempted'])
        for host in ('/tmp/socket', 'x.onion', 'a b', 'host;cmd'):
            with self.assertRaises(ValueError): self.helper.execute('connect', peer=PEER, host=host, port=9735)
        self.assertEqual(self.count('fundchannel'), 0)

    def test_open_repeat_pin_and_close_confirmation(self):
        result = self.open()
        self.assertTrue(result['funding_pin_saved'])
        self.assertEqual(result['channel_state'], 'CHANNELD_NORMAL')
        self.open()
        self.assertEqual(self.count('fundchannel'), 1)
        result = self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
        self.assertEqual(result['phase'], 'close-requested')
        self.assertEqual(self.helper.execute('status')['phase'], 'close-requested')
        self.txs[-1]['blockheight'] = 110
        self.channels = []
        result = self.helper.execute('status')
        self.assertEqual(result['phase'], 'close-confirmed')
        self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
        self.assertEqual(self.count('close'), 1)

    def test_lost_funding_reply_reconciles_exact_inputs_without_resend(self):
        self.lost = 'fundchannel'
        with self.assertRaises(RuntimeError): self.open()
        fresh = c.Channels(self.root, 'xbt-regtest', self.rpc)
        self.assertTrue(fresh.execute('status')['funding_pin_saved'])
        self.open()
        self.assertEqual(self.count('fundchannel'), 1)

    def test_missing_attempt_remains_uncertain_and_never_resubmits(self):
        self.lost = 'fundchannel'
        with self.assertRaises(RuntimeError): self.open()
        self.channels = []; self.txs = []
        self.assertTrue(self.open()['inspection_required'])
        self.assertEqual(self.count('fundchannel'), 1)

    def test_lost_close_reply_never_closes_again(self):
        result = self.open(); self.lost = 'close'
        with self.assertRaises(RuntimeError): self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
        self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
        self.assertEqual(self.count('close'), 1)

    def test_wrong_funding_binding_never_closes(self):
        result = self.open()
        for key, value in [('funding_txid', '77'*32), ('funding_outnum', 1), ('total_msat', 50001000), ('private', False), ('opener', 'remote')]:
            previous = self.channels[0][key]; self.channels[0][key] = value
            with self.assertRaises(ValueError): self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
            self.channels[0][key] = previous
        self.txs[0]['inputs'][0]['txid'] = '88'*32
        with self.assertRaises(ValueError): self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
        self.assertEqual(self.count('close'), 0)

    def test_pending_disconnected_or_not_normal_blocks_close(self):
        result = self.open()
        for key, value in [('htlcs', [{}]), ('peer_connected', False), ('state', 'CHANNELD_AWAITING_LOCKIN')]:
            previous = self.channels[0][key]; self.channels[0][key] = value
            with self.assertRaises(ValueError): self.helper.execute('close', review_code=result['close_review_code'], confirmed=True)
            self.channels[0][key] = previous
        with self.assertRaises(ValueError): self.helper.execute('close', review_code='wrong', confirmed=True)
        with self.assertRaises(ValueError): self.helper.execute('close', review_code=result['close_review_code'], confirmed=False)
        self.assertEqual(self.count('close'), 0)

    def test_caps_confirmation_and_funding_inputs(self):
        for args in ({'confirmed': False}, {'amount_sats': 80001}, {'fee_rate': 11}, {'peer': NODE}):
            with self.assertRaises(ValueError): self.open(**args)
        for change in ({'amount_msat': 59000000}, {'reserved': True}, {'status': 'unconfirmed'}):
            old = self.outputs[0].copy(); self.outputs[0].update(change)
            with self.assertRaises(ValueError): self.open()
            self.outputs[0] = old
        self.closed = [{}]
        with self.assertRaises(ValueError): self.open()
        self.assertEqual(self.count('fundchannel'), 0)

    def test_large_wallet_funds_only_requested_channel_once(self):
        self.outputs[0]['amount_msat'] = 900000000
        result = self.open()
        self.assertEqual(result['channel_sats'], 50000)
        self.open()
        self.assertEqual(self.count('fundchannel'), 1)
        self.assertEqual(c.load(self.root, c.STATE)['inputs'][0]['amount_msat'], 900000000)

    def test_local_validation_visible_rpc_details_private(self):
        self.peers[0]['connected'] = False
        with self.assertRaises(c.ChannelValidationError) as caught:
            self.open()
        self.assertEqual(c.public_error(caught.exception), 'Connect the selected peer first')
        self.assertFalse((self.root / c.STATE).exists())
        for error in (ValueError('private RPC data'), RuntimeError('private RPC data')):
            self.assertNotIn('private RPC data', c.public_error(error))
        self.assertEqual(self.count('fundchannel'), 0)

    def test_existing_channel_or_disconnected_peer_never_funds(self):
        self.channels = [{}]
        with self.assertRaises(ValueError): self.open()
        self.channels = []; self.peers[0]['connected'] = False
        with self.assertRaises(ValueError): self.open()
        self.assertEqual(self.count('fundchannel'), 0)

    def test_wallet_identity_and_changed_repeat_never_mutate(self):
        self.info['network'] = 'bitcoin'
        with self.assertRaises(ValueError): self.open()
        self.info['network'] = 'xbt-regtest'; self.open()
        with self.assertRaises(ValueError): self.open(amount_sats=60000)
        self.info['id'] = '03'+'99'*32
        with self.assertRaises(ValueError): self.helper.execute('status')
        self.assertEqual(self.count('fundchannel'), 1)

    def test_shared_wallet_lock_and_ambiguous_funding_block_withdrawal(self):
        with (self.root / 'wallet-pilot.lock').open('a') as lock:
            c.fcntl.flock(lock, c.fcntl.LOCK_EX | c.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError): self.open()
        self.lost = 'fundchannel'
        with self.assertRaises(RuntimeError): self.open()
        self.channels = []
        from test_wallet_actions import ADDRESS
        with self.assertRaises(ValueError): Wallet(self.root, 'xbt-regtest', self.rpc).execute('prepare', destination=ADDRESS, fee_rate=2, max_fee_sats=2000)
        self.assertEqual(self.count('txprepare'), 0)

    def completed(self):
        r = self.open()
        self.helper.execute('close', review_code=r['close_review_code'], confirmed=True)
        self.txs[-1].update(blockheight=110, inputs=[{'txid': FUNDING, 'index': 0}])
        self.channels[0]['state'] = 'ONCHAIN'
        self.outputs.append({'txid': CLOSE, 'output': 0, 'status': 'confirmed', 'reserved': False, 'amount_msat': 49000000})
        return r['close_review_code']

    def test_archive_preserves_record_and_repeat_never_funds(self):
        code = self.completed()
        before = self.helper.execute('status')
        state = c.load(self.root, c.STATE)
        result = self.helper.execute('archive', review_code=code, confirmed=True)
        self.assertEqual(result['phase'], 'archived')
        self.assertEqual(c.load(self.root, self.helper.archive_name(state)), state)
        self.helper.execute('archive', review_code=code, confirmed=True)
        with self.assertRaises(ValueError): self.open()
        self.assertEqual(self.count('fundchannel'), 1)

    def test_archive_blocks_unconfirmed_wrong_spend_and_reserved_return(self):
        code = self.completed()
        for mutate, undo in [
            (lambda: self.txs[-1].update(blockheight=0), lambda: self.txs[-1].update(blockheight=110)),
            (lambda: self.txs[-1].update(inputs=[]), lambda: self.txs[-1].update(inputs=[{'txid': FUNDING, 'index': 0}])),
            (lambda: self.outputs[-1].update(reserved=True), lambda: self.outputs[-1].update(reserved=False)),
            (lambda: self.channels[0].update(htlcs=[{}]), lambda: self.channels[0].update(htlcs=[])),
        ]:
            mutate()
            with self.assertRaises(ValueError): self.helper.execute('archive', review_code=code, confirmed=True)
            undo()
        self.assertFalse(list(self.root.glob('channel-history-*')))

    def test_archive_crash_between_copy_and_marker_resumes(self):
        code = self.completed();self.helper.execute('status');state=c.load(self.root,c.STATE)
        c.atomic_json(self.root,self.helper.archive_name(state),state)
        self.assertEqual(self.helper.execute('archive',review_code=code,confirmed=True)['phase'],'archived')
        self.assertEqual(self.count('fundchannel'),1)

    def test_archive_mismatch_and_reorg_block_new_attempt(self):
        code=self.completed();self.helper.execute('archive',review_code=code,confirmed=True)
        self.txs[-1]['blockheight']=0
        with self.assertRaises(ValueError):self.open(previous_close_code=code)
        self.txs[-1]['blockheight']=110
        old=c.load(self.root,'channel-history-'+CID+'.json');old['amount_sats']=60000
        c.atomic_json(self.root,'channel-history-'+CID+'.json',old)
        with self.assertRaises(ValueError):self.open(previous_close_code=code)
        self.assertEqual(self.count('fundchannel'),1)

    def test_second_attempt_retains_archive_and_stale_requests_refused(self):
        code=self.completed();self.helper.execute('archive',review_code=code,confirmed=True)
        original=self.rpc; old_txs=copy.deepcopy(self.txs); old_channel=copy.deepcopy(self.channels[0])
        self.outputs=self.outputs[:1]
        def second_rpc(method, **params):
            reply=original(method,**params)
            if method=='fundchannel':
                self.channels[0].update(channel_id='aa'*32,funding_txid='bb'*32)
                self.txs[0]['hash']='bb'*32
                self.channels.append(old_channel);self.txs.extend(old_txs)
                raise RuntimeError('lost second funding reply')
            return reply
        self.helper=c.Channels(self.root,'xbt-regtest',second_rpc)
        with self.assertRaises(RuntimeError):self.open(previous_close_code=code)
        self.assertTrue(self.helper.execute('status')['funding_pin_saved'])
        self.open(previous_close_code=code)
        with self.assertRaises(ValueError):self.open()
        with self.assertRaises(ValueError):self.helper.execute('archive',review_code=code,confirmed=True)
        self.assertEqual(self.count('fundchannel'),2)
        self.assertTrue((self.root/('channel-history-'+CID+'.json')).exists())


if __name__ == '__main__': unittest.main()
