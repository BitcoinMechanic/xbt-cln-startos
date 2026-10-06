import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
import subprocess
import gate as g

NODE = '02' + '11'*32
class Preparation:
    def inspect(self): return {'node_id': NODE}, {'prepared': True}

class Tests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root/'xbt').mkdir()
        (self.root/'xbt/hsm_secret').write_bytes(b'k'*32)
        self.active = False
        self.channels = [dict(state='CHANNELD_NORMAL',peer_connected=True,htlcs=[])]
        self.calls = []
        self.worker = g.Gate(self.root, self.rpc, Preparation())
    def rpc(self, method):
        self.calls.append(method)
        if method == 'getinfo': return dict(id=NODE,network='xbt')
        if method == 'listpeerchannels': return dict(channels=self.channels)
        if method == 'plugin': return dict(plugins=[dict(name=g.PLUGIN,active=True)] if self.active else [])
        if method == 'reverse-pilot-info': return dict(profile=g.PROFILE, gate_active=True)
        raise AssertionError(method)
    def activate(self):
        with patch.object(g, 'source_check'): return self.worker.activate(True)
    def test_optin_and_repeat_no_rewrite(self):
        with self.assertRaises(g.Blocked): self.worker.activate(False)
        self.assertFalse((self.root/g.RECORD).exists())
        result = self.activate()
        self.assertTrue(result['restart_required'])
        path = self.root/g.RECORD
        before = path.stat().st_mtime_ns, path.read_bytes()
        self.activate()
        self.assertEqual(before, (path.stat().st_mtime_ns,path.read_bytes()))
        self.assertFalse(result['payment_started'])
    def test_requires_connected_quiescent_channel(self):
        for channels in ([], [dict(state='CHANNELD_NORMAL',peer_connected=False,htlcs=[])], [dict(state='CHANNELD_NORMAL',peer_connected=True,htlcs=[{}])]):
            self.channels = channels
            with self.assertRaises(g.Blocked): self.activate()
            self.assertFalse((self.root/g.RECORD).exists())
    def test_changed_secret_and_symlink_refused(self):
        self.activate()
        key = self.root/'xbt/hsm_secret'
        key.write_bytes(b'x'*32)
        with self.assertRaises(g.Blocked): g.record(self.root)
        key.unlink(); key.symlink_to('/dev/null')
        with self.assertRaises(g.Blocked): g.key_hash(self.root)
    def test_restored_barrier_and_old_journal_refused(self):
        (self.root/g.BARRIER).write_text('{}')
        with self.assertRaises(g.Blocked): self.activate()
        (self.root/g.BARRIER).unlink()
        path = g.journal_path(self.root); path.parent.mkdir(); path.write_text('{}')
        with self.assertRaises(g.Blocked): self.activate()
        self.assertEqual(path.read_text(),'{}')
    def test_status_checks_running_gate(self):
        self.assertFalse(self.worker.status()['active'])
        self.activate(); self.active=True
        self.assertTrue(self.worker.status()['active'])
        self.assertIn('reverse-pilot-info',self.calls)
        self.assertTrue(set(self.calls) <= {'getinfo','listpeerchannels','plugin','reverse-pilot-info'})
    def test_launch_inert_by_default_bound_when_enabled(self):
        with patch.object(g.os,'execvp') as execute:
            g.launch(self.root,['lightningd','--conf=/dev/null'])
            self.assertEqual(execute.call_args.args[1],['lightningd','--conf=/dev/null'])
        self.activate()
        with patch.object(g,'source_check'), patch.object(g.os,'execvp') as execute, patch.dict(os.environ):
            g.launch(self.root,['lightningd'])
            self.assertIn('--plugin='+g.PLUGIN,execute.call_args.args[1])
            self.assertEqual(os.environ['XBT_GATE_ROOT'],str(self.root))
        (self.root/g.BARRIER).write_text('{}')
        with patch.object(g,'source_check'), patch.object(g.os,'execvp') as execute:
            with self.assertRaises(g.Blocked): g.launch(self.root,['lightningd'])
            execute.assert_not_called()
    def test_bad_source_refused(self):
        path = self.root/'bad.py'; path.write_text('pass')
        with self.assertRaises(g.Blocked): g.source_check(path)
    def test_gate_directory_symlink_refused(self):
        (self.root/'xbt/swap-gate').symlink_to(self.root,target_is_directory=True)
        with self.assertRaises(g.Blocked): self.activate()

    def test_active_recovery_and_changed_node_refused(self):
        self.activate()
        (self.root/'recovery-intent.json').write_text('{"phase":"imported"}')
        with self.assertRaises(g.Blocked):g.record(self.root)
        (self.root/'recovery-intent.json').unlink()
        data=json.loads((self.root/g.RECORD).read_text());data['node_id']='wrong'
        (self.root/g.RECORD).write_text(json.dumps(data))
        with self.assertRaises(g.Blocked):self.worker.status()

    def test_source_bundle_is_exact(self):
        source=Path(os.environ['XBT_GATE_TEST_SOURCE'])
        g.source_check(source)
        with tempfile.TemporaryDirectory() as tmp:
            import shutil
            dest=Path(tmp)/'source';shutil.copytree(source,dest)
            (dest/'reverse_live.py').write_text('pass')
            with self.assertRaises(g.Blocked):g.source_check(dest)

    def test_live_protocol_restart_release_failure_and_unknown_passthrough(self):
        source=Path(os.environ['XBT_GATE_TEST_SOURCE']);g.source_check(source)
        sys.path.insert(0,str(source))
        try:
            from reverse_timing import proposal
            timing=proposal(40)
        finally:sys.path.pop(0)
        self.activate();g.journal_path(self.root).parent.mkdir()
        preimage='ab'*32;payment_hash=hashlib.sha256(bytes.fromhex(preimage)).hexdigest()
        ids=['02'+f'{i:064x}' for i in range(1,5)]
        terms=dict(profile=g.PROFILE,payment_hash=payment_hash,payment_secret='22'*32,
            xbt_amount_msat=350000000,btc_amount_msat=1500000,btc_invoice='lnbc-fixture',
            xbt_channel='1x1x0',expires_at=int(time.time())+300,
            min_cltv_delta=timing['minimum_xbt_remaining_blocks'],max_cltv_delta=2016,
            node_ids=ids[:2],payer_id=ids[2],
            route=[dict(id=ids[3],channel='2x1x0',amount_msat=1500000,delay=40)],
            routing=dict(source=ids[1],destination=ids[3],max_fee_msat=30000,max_delay=576,max_hops=8,final_cltv=40),
            timing=timing,allow_signed_private_final=True)
        init=dict(id=1,method='init',params={'configuration':{'network':'xbt'}})
        hook=dict(id=3,method='htlc_accepted',params={'htlc':dict(short_channel_id='1x1x0',id=8,payment_hash=payment_hash,
            amount_msat=350000000,cltv_expiry=3000,cltv_expiry_relative=1500),'onion':dict(payment_secret='22'*32,
            forward_msat=350000000,total_msat=350000000,type='tlv',outgoing_cltv_value=3000)})
        script="""import os,sys
from pathlib import Path
sys.path.insert(0,os.environ['GATE_MODULE'])
import gate
source=Path(os.environ['XBT_GATE_TEST_SOURCE'])
original=gate.source_check
gate.SOURCE=source
gate.source_check=lambda:original(source)
gate.plugin()
"""
        def run(messages,ok=True):
            env=dict(os.environ,XBT_GATE_ROOT=str(self.root),GATE_MODULE=str(Path(g.__file__).parent))
            result=subprocess.run([sys.executable,'-c',script],input='\n'.join(map(json.dumps,messages)),env=env,text=True,capture_output=True)
            if ok:self.assertEqual(result.returncode,0,result.stderr)
            else:self.assertNotEqual(result.returncode,0);return []
            return [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
        replies=run([dict(id=0,method='getmanifest'),init,dict(id=2,method='reverse-register',params={'quote':terms}),hook])
        self.assertIn('reverse-pilot-info',[m['name'] for m in replies[0]['result']['rpcmethods']])
        journal=g.journal_path(self.root)
        self.assertEqual(json.loads(journal.read_text())[payment_hash]['phase'],'held')
        before=journal.read_bytes()
        run([init,hook,dict(id=4,method='reverse-pilot-info')])
        self.assertEqual(before,journal.read_bytes())
        replies=run([init,hook,dict(id=5,method='reverse-release',params={'payment_hash':payment_hash,'binding':['1x1x0',8],'preimage':preimage})])
        self.assertTrue(any(r.get('result',{}).get('result')=='resolve' for r in replies))
        self.assertEqual(json.loads(journal.read_text())[payment_hash]['phase'],'resolved')
        self.assertTrue(any(r.get('result',{}).get('result')=='resolve' for r in run([init,hook])))
        unknown=json.loads(json.dumps(hook));unknown['params']['htlc']['payment_hash']='ef'*32
        self.assertEqual(run([init,unknown])[-1]['result'],{'result':'continue'})
        # A second quote exercises durable failure replay after the first completes.
        terms['payment_hash']='cd'*32;hook['params']['htlc'].update(payment_hash='cd'*32,id=9)
        run([init,dict(id=2,method='reverse-register',params={'quote':terms}),hook])
        self.assertEqual(json.loads(journal.read_text())['cd'*32]['phase'],'held')
        run([init,hook,dict(id=5,method='reverse-fail',params={'payment_hash':'cd'*32,'binding':['1x1x0',9]})])
        self.assertEqual(run([init,hook])[-1]['result']['result'],'fail')
        init['params']['configuration']['network']='xbt-regtest';run([init],ok=False)

if __name__=='__main__':unittest.main()
