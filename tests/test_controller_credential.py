import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'assets/xbt'))
from controller_credential import Credentials, RECORD, RESTRICTIONS, Blocked

class CredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.id='02'+'12'*32
        self.calls=[];self.blacklisted=False;self.lost=None;self.rules=copy.deepcopy(RESTRICTIONS)
        prep=Mock();prep.inspect.return_value=({'node_id':self.id},{'prepared':True})
        self.worker=Credentials(self.root,self.rpc,prep)
    def rpc(self,method,**params):
        self.calls.append((method,params))
        if method=='getinfo': return dict(id=self.id,network='xbt')
        if method=='createrune':
            self.assertEqual(params,dict(restrictions=RESTRICTIONS))
            if self.lost=='create': raise RuntimeError('secret')
            return dict(rune='test-rune',unique_id='7')
        if method=='showrunes':
            rules=[]
            for rule in self.rules:
                rules.append(dict(alternatives=[dict(fieldname=a.split('=')[0],condition='=',value=a.split('=')[1]) for a in rule]))
            return dict(runes=[dict(unique_id='7',restrictions=rules,blacklisted=self.blacklisted)])
        if method=='blacklistrune':
            self.assertEqual(params,dict(start=7,end=7));self.blacklisted=True
            if self.lost=='revoke':raise RuntimeError('secret')
            return {}
        raise AssertionError(method)
    def count(self,m):return sum(x[0]==m for x in self.calls)
    def test_create_repeat_private_record(self):
        first=self.worker.create(True);self.assertEqual(first,self.worker.create(True))
        self.assertEqual(self.count('createrune'),1)
        self.assertEqual((self.root/RECORD).stat().st_mode&0o777,0o600)
    def test_status_never_returns_rune(self):
        self.worker.create(True);self.assertNotIn('test-rune',json.dumps(self.worker.status()))
    def test_confirmation_before_rpc(self):
        for op in (self.worker.create,self.worker.revoke):
            with self.assertRaises(Blocked):op(False)
        self.assertEqual(self.calls,[])
    def test_lost_create_never_mints_again(self):
        self.lost='create'
        with self.assertRaises(RuntimeError):self.worker.create(True)
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertEqual(self.count('createrune'),1)
        self.assertEqual(self.worker.status()['phase'],'creating')
    def test_lost_revoke_reconciles_without_second_rpc(self):
        self.worker.create(True);self.lost='revoke'
        with self.assertRaises(RuntimeError):self.worker.revoke(True)
        self.assertEqual(self.worker.revoke(True)['phase'],'revoked')
        self.assertEqual(self.count('blacklistrune'),1)
    def test_revoke_repeat_and_no_automatic_rotation(self):
        self.worker.create(True);self.worker.revoke(True);self.worker.revoke(True)
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertEqual(self.count('createrune'),1);self.assertEqual(self.count('blacklistrune'),1)
    def test_wrong_identity_blocks_mutation(self):
        self.worker.create(True);self.id='03'+'34'*32
        with self.assertRaises(Blocked):self.worker.revoke(True)
        self.assertEqual(self.count('blacklistrune'),0)
    def test_changed_restrictions_block_export_and_revoke(self):
        self.worker.create(True);self.rules=[]
        for op in (self.worker.create,self.worker.revoke):
            with self.assertRaises(Blocked):op(True)
        self.assertEqual(self.count('blacklistrune'),0)
    def test_missing_preparation_blocks_creation(self):
        self.worker.preparation.inspect.return_value=({'node_id':self.id},{'prepared':False})
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertEqual(self.count('createrune'),0)
    def test_symlink_record_refused(self):
        (self.root/RECORD).symlink_to(self.root/'missing')
        with self.assertRaises(Blocked):self.worker.status()
    def test_real_preparation_blocks_recovery_before_creation(self):
        from coordinator import Preparation
        for marker in ('restore-blocked', 'recovery-intent.json'):
            (self.root/marker).write_text('{}')
            preparation=Preparation(self.root, rpc=lambda method: dict(id=self.id,network='xbt'))
            worker=Credentials(self.root,self.rpc,preparation)
            with patch('coordinator.check_bundle'), self.assertRaises(ValueError):
                worker.create(True)
            (self.root/marker).unlink()
        self.assertEqual(self.count('createrune'),0)
    def test_revocation_disappeared_is_not_silently_accepted(self):
        self.worker.create(True);self.worker.revoke(True);self.blacklisted=False
        with self.assertRaises(Blocked):self.worker.status()

if __name__=='__main__':unittest.main()
