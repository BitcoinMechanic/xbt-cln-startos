#!/usr/bin/env python3
"""Bounded invoice/payment actions with durable no-resubmission records."""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time

from empty_backup import atomic_json
from recovery import load
from wallet_actions import Wallet


class Refusal(ValueError):
    pass


def need(ok, message):
    if not ok:
        raise Refusal(message)


def number(n, low, high):
    need(type(n) is int and low <= n <= high, 'Amount or fee is outside the pilot bounds.')
    return n


class Lightning(Wallet):
    def name(self, reference):
        need(isinstance(reference, str) and re.fullmatch('[0-9a-f]{64}', reference), 'Invalid payment reference.')
        return 'lightning-payment-' + reference + '.json'

    def decode(self, invoice, fresh=True):
        need(isinstance(invoice, str) and 0 < len(invoice) <= 16000 and not any(c.isspace() for c in invoice), 'Paste one complete invoice without whitespace.')
        d = self.rpc('decode', string=invoice)
        need(d.get('valid') is True and d.get('type') == 'bolt11 invoice', 'A valid BOLT11 invoice is required.')
        need(d.get('currency') == ('xbt' if self.network == 'xbt' else 'xbtrt'), 'Invoice is not on this XBT network.')
        number(d.get('amount_msat'), 1000, 10000000)
        need(d['amount_msat'] % 1000 == 0, 'Use a whole-satoshi invoice, at most 10,000 sats.')
        need('description_hash' not in d, 'Description-hash invoices are not supported by this pilot.')
        need(re.fullmatch('0[23][0-9a-f]{64}', d.get('payee', '')) is not None, 'Invalid invoice destination.')
        self.name(d.get('payment_hash'))
        if fresh:
            need(d['created_at'] + d['expiry'] > int(time.time()), 'Invoice has expired; nothing was submitted.')
        return d

    def binding(self, s):
        return hashlib.sha256(json.dumps({k: s[k] for k in ('node_id', 'network', 'invoice', 'max_fee_sats')}, sort_keys=True).encode()).hexdigest()[:16]

    def record(self, reference):
        s = load(self.root, self.name(reference))
        need(s['node_id'] == self.ready() and s['network'] == self.network, 'Saved payment belongs to another wallet.')
        d = self.decode(s['invoice'], fresh=False)
        need(d['payment_hash'] == reference and d['amount_msat'] == s['amount_msat'] and d['payee'] == s['payee'], 'Saved invoice binding changed.')
        number(s['max_fee_sats'], 0, 100)
        need(s['review_code'] == self.binding(s), 'Saved review changed.')
        return s

    def summary(self, s):
        return {k: s[k] for k in ('reference', 'phase', 'review_code', 'payee', 'amount_msat', 'max_fee_sats', 'expires_at')} | {'automatic_resubmission': False}

    def review(self, invoice, max_fee_sats):
        node = self.ready()
        number(max_fee_sats, 0, 100)
        d = self.decode(invoice)
        need(d['payee'] != node, 'Self-payment is not supported by this pilot.')
        ref = d['payment_hash']
        if os.path.lexists(self.root / self.name(ref)):
            s = self.record(ref)
            need(s['invoice'] == invoice and s['max_fee_sats'] == max_fee_sats, 'An existing review has different terms. Use its payment status.')
            return self.status(ref)
        need(not self.rpc('listpays', payment_hash=ref)['pays'], 'This invoice already has a wallet payment record; inspect it locally.')
        s = dict(reference=ref, node_id=node, network=self.network, invoice=invoice,
                 phase='reviewed', amount_msat=d['amount_msat'], payee=d['payee'],
                 max_fee_sats=max_fee_sats, expires_at=d['created_at']+d['expiry'])
        s['review_code'] = self.binding(s)
        atomic_json(self.root, self.name(ref), s)
        return self.summary(s)

    def status(self, reference):
        s = self.record(reference)
        rows = self.rpc('listpays', payment_hash=reference)['pays']
        result = self.summary(s)
        if s['phase'] == 'reviewed':
            result['existing_payment_detected'] = bool(rows)
            return result
        if not rows:
            return result | {'phase': 'outcome-unknown', 'inspection_required': True}
        need(len(rows) == 1, 'Ambiguous wallet payment history; inspect locally.')
        p = rows[0]
        need(p['payment_hash'] == reference and p.get('bolt11') == s['invoice'], 'Wallet payment does not match saved invoice.')
        need(p.get('label') == 'startos-'+reference, 'Wallet payment label does not match this attempt.')
        need(p['status'] in ('pending', 'complete', 'failed'), 'Unknown wallet payment state.')
        if p['status'] == 'complete':
            need(p.get('destination') == s['payee'] and p.get('amount_msat') == s['amount_msat'], 'Completed payment amount or destination mismatch.')
            sent = p['amount_sent_msat']
            need(type(sent) is int and s['amount_msat'] <= sent <= s['amount_msat']+s['max_fee_sats']*1000, 'Completed payment exceeds the reviewed fee limit.')
            need(hashlib.sha256(bytes.fromhex(p['preimage'])).hexdigest() == reference, 'Payment proof mismatch.')
            result['routing_fee_msat'] = sent-s['amount_msat']
        return result | {'phase': p['status']}

    def pay(self, reference, review_code, confirmed=False):
        need(confirmed is True, 'Payment confirmation is required.')
        s = self.record(reference)
        need(review_code == s['review_code'], 'Review code does not match.')
        if s['phase'] != 'reviewed':
            return self.status(reference)
        self.decode(s['invoice'])
        need(not self.rpc('listpays', payment_hash=reference)['pays'], 'A wallet payment already exists; no new attempt was submitted.')
        s['phase'] = 'submitted'
        atomic_json(self.root, self.name(reference), s)
        try:
            self.rpc('pay', bolt11=s['invoice'], maxfee=s['max_fee_sats']*1000,
                     retry_for=30, maxdelay=144, label='startos-'+reference)
        except Exception:
            # A timeout or RPC error cannot prove whether CLN accepted the call.
            pass
        return self.status(reference)

    def invoice(self, label, amount_sats):
        self.ready()
        need(isinstance(label, str) and re.fullmatch('[A-Za-z0-9_-]{1,48}', label), 'Use a short invoice label containing letters, numbers, hyphens or underscores.')
        number(amount_sats, 1, 10000)
        full = 'startos-invoice-'+label
        rows = self.rpc('listinvoices', label=full)['invoices']
        if not rows:
            # CLN atomically enforces label uniqueness, including a lost reply.
            self.rpc('invoice', amount_msat=amount_sats*1000, label=full,
                     description='StartOS XBT payment', expiry=3600)
            rows = self.rpc('listinvoices', label=full)['invoices']
        need(len(rows) == 1 and rows[0]['amount_msat'] == amount_sats*1000, 'This label already has a different amount.')
        return self.invoice_status(label)

    def invoice_status(self, label):
        self.ready()
        need(isinstance(label, str) and re.fullmatch('[A-Za-z0-9_-]{1,48}', label), 'Invalid invoice label.')
        rows = self.rpc('listinvoices', label='startos-invoice-'+label)['invoices']
        need(len(rows) == 1, 'Invoice label was not found.')
        i = rows[0]
        return dict(label=label, phase=i['status'], invoice=i['bolt11'], amount_msat=i['amount_msat'],
                    received_msat=i.get('amount_received_msat', 0), expires_at=i['expires_at'])

    def execute(self, operation, **params):
        with (self.root / 'wallet-pilot.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            need(operation in ('review', 'pay', 'status', 'invoice', 'invoice_status'), 'Unknown Lightning action.')
            return getattr(self, operation)(**params)


if __name__ == '__main__':
    os.umask(0o077)
    try:
        print(json.dumps(Lightning(Path(sys.argv[1]).resolve(strict=True)).execute(**json.loads(sys.stdin.read(20000)))))
    except Exception as e:
        print(json.dumps({'error': str(e) if isinstance(e, Refusal) else 'Action interrupted or RPC unavailable. Check the saved payment reference or invoice label; private details withheld.'}))
        sys.exit(1)
