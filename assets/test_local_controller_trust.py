"""Use the sealed coordinator's real journals and authority, with read-only RPC fixtures."""
import copy
import unittest
from unittest.mock import patch
import local_controller_trust as lt
import bounded_authority as ba
import chain_identity as ci
import held_gate as hg
import restore_barrier as rb
from test_coordinator_admin import AdminTests

class TrustTests(AdminTests):
    # Reuse setup helpers, not inherited test cases.
    def open(self, profile=None, fresh=False):
        super().open(profile, fresh)
        path=self.root/lt.DIRECTORY
        if fresh:lt.initialize(path,self.node.chain)
        self.js.append(hg.Journal(path));self.trust=lt.Trust(self.admin,self.js[-1])
    def test_automatic_both_profiles_restart_and_renewal(self):
        for profile in (ci.BTC, ci.PRIVKEYIO_XBT):
            if profile!=ci.BTC:
                self.close();self.root=self.root/'xbt';self.root.mkdir(mode=0o700);self.open(profile,True)
            self.assertEqual(self.trust.maintain()['state'],'ready')
            current=copy.deepcopy(self.auth.record['current'])
            self.open();self.assertEqual(self.trust.maintain()['state'],'ready')
            self.assertEqual(current,self.auth.record['current'])
            self.now+=86101;self.open();self.assertEqual(self.trust.maintain()['state'],'ready')
            self.assertTrue(all(current[k]!=self.auth.record['current'][k] for k in ba.KINDS))
            self.assertEqual(len(self.auth.record['grants']),4)
            self.assertTrue(all(m in ('getinfo','listpeerchannels') for m,_ in self.node.calls))
    def test_empty_nodes_wait_then_get_authority(self):
        rows=self.node.rows;self.node.rows=[]
        self.assertEqual(set(self.trust.maintain()['roles'].values()),{'waiting_for_channels'})
        self.assertEqual(self.auth.record['grants'],{})
        self.node.rows=rows;self.assertEqual(self.trust.maintain()['state'],'ready')
    def test_lost_writes_retry_without_duplicate_authority(self):
        for boundary in ('intent','authority','review','owned'):
            with self.subTest(boundary=boundary):
                if self.auth.record['grants']:
                    self.close();self.root=self.root/boundary;self.root.mkdir(mode=0o700);self.open(ci.BTC,True)
                journal=self.js[{'intent':2,'authority':0,'review':1,'owned':2}[boundary]]
                write=journal.write;hit=[]
                def lost(r):
                    write(r)
                    if not hit and (boundary not in ('intent','owned') or (r['pending'] is not None if boundary=='intent' else len(r['owned'])>0)):
                        hit.append(True);raise OSError('lost reply')
                with patch.object(journal,'write',side_effect=lost),self.assertRaises(hg.StorageError):self.trust.maintain()
                self.open();self.assertEqual(self.trust.maintain()['state'],'ready')
                self.assertEqual(len(self.auth.record['grants']),2)
                self.assertEqual(len(self.trust.r['owned']),2)
    def test_disable_and_manual_pause_survive_restart(self):
        self.trust.maintain();old=list(self.trust.r['owned']);self.trust.disable();self.open()
        self.assertFalse(self.trust.maintain()['enabled'])
        self.assertTrue(all(self.auth.record['grants'][g]['paused'] for g in old))
        self.trust.enable();self.assertEqual(self.trust.maintain()['state'],'ready')
        self.auth.pause(self.auth.record['current']['outgoing']);self.open()
        self.assertEqual(self.trust.maintain()['state'],'paused');self.open()
        self.assertFalse(self.trust.maintain()['enabled'])
    def test_disable_preserves_unrelated_manual_grant(self):
        gid=self.review();self.confirm(gid)
        self.trust.maintain();self.trust.disable()
        self.assertFalse(self.auth.record['grants'][gid]['paused'])
    def test_exhausted_slot_budget_renews_without_refunding_old_entries(self):
        self.trust.maintain();gid=self.auth.record['current']['outgoing']
        for n in range(4):
            self.node.decoded['payment_hash']=('%02x' % (n+1))*32
            data=self.node.plan();self.node.plan_value=data
            eid=self.auth.enroll(gid,data,confirmed=True);self.auth.retire(eid,confirmed=True)
        self.assertEqual(len(self.auth.record['entries']),4)
        self.open();self.assertEqual(self.trust.maintain()['state'],'ready')
        self.assertNotEqual(gid,self.auth.record['current']['outgoing'])
        self.assertEqual(len(self.auth.record['entries']),4)
        self.assertFalse(any(m=='sendpay' for m,_ in self.node.calls))
    def test_lost_disable_reply_finishes_revocation_on_restart(self):
        self.trust.maintain();write=self.js[0].write
        def lost(r):write(r);raise OSError('lost pause reply')
        with patch.object(self.js[0],'write',side_effect=lost),self.assertRaises(hg.StorageError):self.trust.disable()
        self.open();self.assertFalse(self.trust.maintain()['enabled'])
        self.assertTrue(all(v['paused'] for v in self.auth.record['grants'].values()))
    def test_pause_after_lost_install_reply_cannot_be_bypassed(self):
        write=self.js[0].write
        def lost(r):write(r);raise OSError('lost install reply')
        with patch.object(self.js[0],'write',side_effect=lost),self.assertRaises(hg.StorageError):self.trust.maintain()
        self.open();gid=next(iter(self.auth.record['grants']));self.auth.pause(gid)
        self.open();self.assertEqual(self.trust.maintain()['state'],'paused')
        self.assertEqual(len(self.auth.record['grants']),1)
        self.assertTrue(self.auth.record['grants'][gid]['paused'])
    def test_pending_swap_prevents_renewal(self):
        self.trust.maintain();before=copy.deepcopy(self.auth.record['grants'])
        self.now+=86401;self.auth.record['entries']['fixture']={}
        self.assertEqual(self.trust.maintain()['state'],'waiting_for_recovery')
        self.assertEqual(before,self.auth.record['grants'])
    def test_restore_and_missing_owned_authority_fail_closed(self):
        self.trust.maintain();before=self.js[0].read();rb.fence(self.root)
        with self.assertRaises(ValueError):self.trust.maintain()
        self.assertEqual(before,self.js[0].read())
    def test_capacity_limit_is_reported_without_deleting_history(self):
        self.trust.maintain();self.now+=86401
        with patch.object(ba,'MAX_RECORDS',2):
            self.assertEqual(set(self.trust.maintain()['roles'].values()),{'history_full'})
        self.assertEqual(len(self.auth.record['grants']),2)

if __name__=='__main__':unittest.main()
