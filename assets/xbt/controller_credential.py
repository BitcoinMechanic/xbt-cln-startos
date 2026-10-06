#!/usr/bin/env python3
"""One identity-bound read-only rune, with durable creation and revocation intent."""
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
from coordinator import Preparation
from empty_backup import atomic_json
from recovery import load as recovery_load

class Blocked(ValueError):
    pass

def require(condition, reason):
    if not condition: raise Blocked(reason)

def load(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'nonregular_record')
    return recovery_load(path.parent, path.name)

def save(path, data):
    atomic_json(path.parent, path.name, data)

from read_only_rpc import RESTRICTIONS

RECORD = 'controller-read-only.json'

class Credentials:
    record_name = RECORD
    restrictions = RESTRICTIONS
    def __init__(self, root, rpc=None, preparation=None, network="xbt"):
        require(network in ("xbt", "xbt-regtest"), "wrong_network")
        self.network = network
        self.root = Path(root)
        self.rpc = rpc or self.call
        self.preparation = preparation or Preparation(root, network)

    def call(self, method, **params):
        require(method in ('getinfo', 'createrune', 'showrunes', 'blacklistrune'), 'unexpected_rpc')
        result = subprocess.run(['lightning-cli', '--lightning-dir='+str(self.root),
            '--network='+self.network, '--json', '--notifications=none', '-k', method,
            *[k+'='+(v if isinstance(v,str) else json.dumps(v)) for k,v in params.items()]], capture_output=True, text=True, timeout=30)
        require(result.returncode == 0, 'credential_rpc_unavailable')
        reply = json.loads(result.stdout)
        require('error' not in reply, 'credential_rpc_unavailable')
        return reply

    def record(self):
        path = self.root/self.record_name
        if not os.path.lexists(path): return None
        r = load(path)
        info = self.rpc('getinfo')
        require(r.get('schema') == 1 and r.get('node_id') == info.get('id')
            and r.get('network') == info.get('network') == self.network, 'credential_binding_changed')
        require(r.get('phase') in ('creating','active','revoking','revoked'), 'invalid_credential_record')
        if r['phase'] != 'creating':
            require(isinstance(r.get('rune'),str) and re.fullmatch(r'[A-Za-z0-9_+=/-]{1,8192}',r['rune']), 'invalid_credential_record')
            require(isinstance(r.get('unique_id'),str) and re.fullmatch(r'[0-9]+',r['unique_id']), 'invalid_credential_record')
        return r

    def verify(self, r):
        items = self.rpc('showrunes', rune=r['rune'])['runes']
        require(len(items)==1, 'credential_not_found')
        item=items[0]
        require(item.get('unique_id') == r['unique_id'] and item.get('our_rune',True)
            and item.get('stored',True), 'credential_binding_changed')
        actual = [[a['fieldname']+a['condition']+a['value'] for a in rule['alternatives']]
                  for rule in item['restrictions']]
        require(actual == self.restrictions, 'credential_restrictions_changed')
        return item.get('blacklisted',False)

    def status(self):
        r=self.record()
        phase='not_created' if r is None else r['phase']
        if r is not None and phase in ('active','revoking','revoked'):
            blacklisted=self.verify(r)
            if blacklisted: phase='revoked'
            elif phase=='revoked': raise Blocked('revocation_no_longer_effective')
        return dict(phase=phase, read_only=True, payment_started=False)

    def create(self, confirmed):
        require(confirmed is True, 'confirmation_required')
        binding,status=self.preparation.inspect()
        require(status['prepared'], 'preparation_required')
        r=self.record()
        if r is None:
            r=dict(schema=1,node_id=binding['node_id'],network=self.network,phase='creating')
            save(self.root/self.record_name,r)
            # Never retry this RPC if the reply or subsequent save is lost.
            reply=self.rpc('createrune', restrictions=self.restrictions)
            r.update(rune=reply['rune'],unique_id=reply['unique_id'],phase='active')
            save(self.root/self.record_name,r)
        require(r['phase']=='active', 'credential_needs_inspection_or_is_revoked')
        require(not self.verify(r), 'credential_revoked')
        return dict(phase='active',rune=r['rune'],read_only=True,payment_started=False)

    def revoke(self, confirmed):
        require(confirmed is True, 'confirmation_required')
        r=self.record()
        require(r is not None and r['phase']!='creating','credential_needs_inspection')
        if not self.verify(r):
            require(r['phase']!='revoked','revocation_no_longer_effective')
            r['phase']='revoking';save(self.root/self.record_name,r)
            self.rpc('blacklistrune',start=int(r['unique_id']),end=int(r['unique_id']))
            require(self.verify(r), 'revocation_not_confirmed')
        r['phase']='revoked';save(self.root/self.record_name,r)
        return dict(phase='revoked',read_only=True,payment_started=False)


def main(worker_type=Credentials, lock_name="controller-read-only.lock"):
    os.umask(0o077)
    try:
        root=Path(sys.argv[1]);request=json.load(sys.stdin)
        fd=os.open(root/lock_name,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
        with os.fdopen(fd,'a') as lock:
            require(stat.S_ISREG(os.fstat(lock.fileno()).st_mode),'nonregular_lock')
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
            worker=worker_type(root)
            op=request.get('operation')
            if op=='status': result=worker.status()
            elif op=='create': result=worker.create(request.get('confirmed'))
            elif op=='revoke': result=worker.revoke(request.get('confirmed'))
            else: raise Blocked('unknown_operation')
        print(json.dumps(result))
    except Exception as error:
        print(json.dumps(dict(error='Controller credential action failed.',
            reason=str(error) if isinstance(error,Blocked) else 'private_details_withheld')))
        raise SystemExit(1)

if __name__=='__main__': main()
