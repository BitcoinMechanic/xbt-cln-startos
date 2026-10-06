import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'assets/xbt'))
from gate_credential import GateCredentials
from controller_credential import Credentials, RESTRICTIONS, Blocked

class GateCredentialTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.calls=[];self.revoked=False;self.lost=False
        self.rules=copy.deepcopy(GateCredentials.restrictions)
        self.identity='02'+'12'*32
        prep=Mock();prep.inspect.return_value=({'node_id':self.identity},{'prepared':True})
        self.worker=GateCredentials(self.root,self.rpc,prep)
        self.gate=patch('gate_credential.Gate').start();self.addCleanup(patch.stopall)
        self.gate.return_value.status.return_value={'active':True,'restored_gate_blocked':False}
    def rpc(self,method,**params):
        self.calls.append((method,params))
        if method=='getinfo':return {'id':self.identity,'network':'xbt'}
        if method=='createrune':
            self.assertEqual(params['restrictions'],[['method=getinfo','method=reverse-pilot-info'],['pnum=0']])
            if self.lost:raise RuntimeError('lost')
            return {'rune':'gate-rune','unique_id':'31'}
        if method=='showrunes':return {'runes':[{'unique_id':'31','blacklisted':self.revoked,'restrictions':[{'alternatives':[dict(fieldname=a.split('=')[0],condition='=',value=a.split('=')[1]) for a in rule]} for rule in self.rules]}]}
        if method=='blacklistrune':
            self.assertEqual(params,{'start':31,'end':31});self.revoked=True;return {}
        raise AssertionError(method)
    def test_separate_scope_record_and_repeat(self):
        monitor=self.root/Credentials.record_name;monitor.write_text('retained monitor record')
        self.worker.create(True);self.worker.create(True)
        self.assertEqual(sum(m=='createrune' for m,p in self.calls),1)
        self.assertEqual(monitor.read_text(),'retained monitor record')
        self.assertEqual(Credentials.restrictions,RESTRICTIONS)
        self.assertNotEqual(Credentials.restrictions,GateCredentials.restrictions)
        self.assertEqual((self.root/GateCredentials.record_name).stat().st_mode&0o777,0o600)
        self.assertNotIn('gate-rune',json.dumps(self.worker.status()))
    def test_gate_required_and_confirmation_first(self):
        with self.assertRaises(Blocked):self.worker.create(False)
        self.gate.assert_not_called()
        self.gate.return_value.status.return_value['active']=False
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertEqual(self.calls,[])
    def test_lost_creation_is_not_retried(self):
        self.lost=True
        with self.assertRaises(RuntimeError):self.worker.create(True)
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertEqual(sum(m=='createrune' for m,p in self.calls),1)
    def test_revoke_while_gate_inactive(self):
        self.worker.create(True);self.gate.return_value.status.side_effect=RuntimeError('stopped')
        self.worker.revoke(True);self.worker.revoke(True)
        self.assertEqual(sum(m=='blacklistrune' for m,p in self.calls),1)
        self.assertEqual(self.worker.status()['phase'],'revoked')
    def test_widened_scope_refused(self):
        self.worker.create(True);self.rules=[['method=getinfo','method=sendpay']]
        with self.assertRaises(Blocked):self.worker.create(True)
        self.assertFalse(self.revoked)

if __name__=='__main__':unittest.main()
