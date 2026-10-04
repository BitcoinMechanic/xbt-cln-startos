import copy
import hashlib
from pathlib import Path
import sys
import tempfile
import time
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
from lightning_actions import Lightning, Refusal
from recovery import load

NODE, PEER = '02'+'11'*32, '03'+'22'*32
PREIMAGE = '33'*32
HASH = hashlib.sha256(bytes.fromhex(PREIMAGE)).hexdigest()

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.info = {'network':'xbt-regtest', 'id':NODE}
        self.d = dict(valid=True, type='bolt11 invoice', currency='xbtrt', payee=PEER,
                      payment_hash=HASH, amount_msat=1000000, created_at=int(time.time()), expiry=3600)
        self.rows, self.invoices, self.calls = [], [], []
        self.lost = False
        self.h = Lightning(self.root, 'xbt-regtest', self.rpc)
    def rpc(self, method, **p):
        self.calls.append((method,p))
        if method == 'getinfo': return self.info
        if method == 'decode': return copy.deepcopy(self.d)
        if method == 'listpays': return {'pays':copy.deepcopy(self.rows)}
        if method == 'listinvoices': return {'invoices':copy.deepcopy(self.invoices)}
        if method == 'invoice':
            self.invoices = [dict(label=p['label'], amount_msat=p['amount_msat'], bolt11='testinvoice', status='unpaid', expires_at=9999999999)]
            if self.lost: raise TimeoutError()
            return self.invoices[0]
        if method == 'pay':
            self.assertEqual(load(self.root, self.h.name(HASH))['phase'], 'submitted')
            self.assertEqual(p['maxfee'],1000)
            self.assertEqual(p['maxdelay'],144)
            self.rows = [dict(payment_hash=HASH, status='complete', bolt11=p['bolt11'], label=p['label'], destination=PEER, amount_msat=1000000, amount_sent_msat=1000000, preimage=PREIMAGE)]
            if self.lost: raise TimeoutError()
            return {}
        raise AssertionError(method)
    def review(self): return self.h.execute('review', invoice='testinvoice', max_fee_sats=1)
    def pay(self, r): return self.h.execute('pay', reference=r['reference'], review_code=r['review_code'], confirmed=True)
    def sends(self): return sum(m=='pay' for m,p in self.calls)
    def test_review_never_spends_and_repeat_is_stable(self):
        a=self.review(); b=self.review(); self.assertEqual(a['review_code'],b['review_code']); self.assertEqual(self.sends(),0)
    def test_complete_and_repeat_do_not_resend(self):
        r=self.review();self.assertEqual(self.pay(r)['phase'],'complete');self.pay(r);self.assertEqual(self.sends(),1)
    def test_lost_reply_recovers_without_resubmission(self):
        r=self.review();self.lost=True;self.assertEqual(self.pay(r)['phase'],'complete');self.pay(r);self.assertEqual(self.sends(),1)
    def test_missing_pending_failed_records_never_resend(self):
        r=self.review();self.pay(r)
        original=copy.deepcopy(self.rows)
        for phase in ('pending','failed'):
            self.rows=copy.deepcopy(original);self.rows[0]['status']=phase
            self.assertEqual(self.pay(r)['phase'],phase)
        self.rows=[];self.assertEqual(self.pay(r)['phase'],'outcome-unknown');self.assertEqual(self.sends(),1)
    def test_expired_before_send_preserves_review(self):
        r=self.review();self.d['created_at']=0
        with self.assertRaises(Refusal): self.pay(r)
        self.assertEqual(self.sends(),0)
        self.assertEqual(load(self.root,self.h.name(HASH))['phase'],'reviewed')
    def test_confirmation_and_review_code_required(self):
        r=self.review()
        for args in [dict(confirmed=False,review_code=r['review_code']),dict(confirmed=True,review_code='bad')]:
            with self.assertRaises(Refusal): self.h.execute('pay',reference=HASH,**args)
        self.assertEqual(self.sends(),0)
    def test_wrong_network_amount_and_invalid_invoice(self):
        for k,v in [('currency','bc'),('valid',False),('amount_msat',10000001),('amount_msat',1001),('payee',NODE)]:
            old=self.d[k];self.d[k]=v
            with self.assertRaises(Refusal):self.review()
            self.d[k]=old
        self.assertEqual(self.sends(),0)
    def test_existing_payment_blocks_new_submission(self):
        r=self.review();self.rows=[{}]
        with self.assertRaises(Refusal):self.pay(r)
        self.assertEqual(self.sends(),0)
    def test_changed_wallet_or_saved_fee_is_refused(self):
        r=self.review();self.info['id']=PEER
        with self.assertRaises(Refusal):self.pay(r)
        self.info['id']=NODE
        from empty_backup import atomic_json
        s=load(self.root,self.h.name(HASH));s['max_fee_sats']=99;atomic_json(self.root,self.h.name(HASH),s)
        with self.assertRaises(Refusal):self.pay(r)
        self.assertEqual(self.sends(),0)
    def test_proof_amount_fee_and_label_mismatch_refused(self):
        r=self.review();self.pay(r)
        for k,v in [('preimage','44'*32),('amount_sent_msat',1001001),('amount_msat',900000),('label','other')]:
            old=self.rows[0][k];self.rows[0][k]=v
            with self.assertRaises(Refusal):self.pay(r)
            self.rows[0][k]=old
        self.assertEqual(self.sends(),1)
    def test_invoice_lost_reply_and_repeat_return_original(self):
        self.lost=True
        with self.assertRaises(TimeoutError): self.h.execute('invoice',label='one',amount_sats=1000)
        self.lost=False
        r=self.h.execute('invoice',label='one',amount_sats=1000)
        self.assertEqual(r['invoice'],'testinvoice')
        self.assertEqual(sum(m=='invoice' for m,p in self.calls),1)
        with self.assertRaises(Refusal):self.h.execute('invoice',label='one',amount_sats=2000)
    def test_concurrent_action_is_refused(self):
        import fcntl
        with (self.root/'wallet-pilot.lock').open('a') as f:
            fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):self.review()
        self.assertEqual(self.calls,[])

if __name__=='__main__':unittest.main()
