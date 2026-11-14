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
    def xbt_liquidity(self):
        self.close();self.root=self.root/'xbt';self.root.mkdir(mode=0o700)
        self.open(ci.PRIVKEYIO_XBT,True)
        self.node.rows[0].update(spendable_msat=20000000000,receivable_msat=20000000000)
    def extra_channel(self):
        row=copy.deepcopy(self.node.rows[0])
        row.update(channel_id='88'*32,funding_txid='99'*32,short_channel_id='120x1x0',
                   spendable_msat=20000000000,receivable_msat=20000000000)
        self.node.rows.append(row)
        return row
    def test_smaller_ready_channel_remains_eligible_below_grant_ceiling(self):
        self.node.rows[0].update(spendable_msat=300000000,receivable_msat=300000000)
        self.trust.maintain();old=copy.deepcopy(self.auth.record['current'])
        small=self.extra_channel();small.update(spendable_msat=65296000,receivable_msat=30000000)
        self.trust.maintain()
        for kind in ba.KINDS:
            g=self.auth.record['grants'][self.auth.record['current'][kind]]['terms']
            self.assertIn(small['channel_id'],[p['channel_id'] for p in g['channels']])
            self.assertEqual(g['limits']['max_amount_msat'],100000000)
            self.assertNotEqual(old[kind],self.auth.record['current'][kind])
        stable=copy.deepcopy(self.auth.record['current']);self.trust.maintain()
        self.assertEqual(stable,self.auth.record['current'])

    def test_closed_historical_channel_does_not_block_renewal(self):
        self.trust.maintain();old=copy.deepcopy(self.auth.record['current'])
        gid=old['outgoing'];data=self.node.plan();self.node.plan_value=data
        eid=self.auth.enroll(gid,data,confirmed=True);self.auth.retire(eid,confirmed=True)
        receipt=copy.deepcopy(self.auth.record['entries'][eid])
        self.node.rows[0]['state']='ONCHAIN';new=self.extra_channel();new['state']='CHANNELD_NORMAL'
        self.trust.maintain()
        for kind in ba.KINDS:
            g=self.auth.record['grants'][self.auth.record['current'][kind]]['terms']
            self.assertEqual([p['channel_id'] for p in g['channels']],[new['channel_id']])
            self.assertNotEqual(old[kind],self.auth.record['current'][kind])
        self.assertEqual(receipt,self.auth.record['entries'][eid])
        current=copy.deepcopy(self.auth.record['current']);self.trust.maintain()
        self.assertEqual(current,self.auth.record['current'])
    def test_completed_payment_rechecks_live_history_and_accepts_verified_closed_pin(self):
        self.trust.maintain();gid=self.auth.record['current']['outgoing']
        data=self.node.plan();self.node.plan_value=data
        eid=self.auth.enroll(gid,data,confirmed=True);self.auth.send(eid)
        self.node.finish();self.auth.reconcile(eid)
        self.assertTrue(self.auth.status(eid)['terminal'])
        self.node.history_rows=[]
        with self.assertRaisesRegex(ValueError,'original_htlc_missing'):self.auth.prior()
        self.node.rows[0]['state']='ONCHAIN';self.auth.prior()
        self.node.rows[0]['htlcs']=[{}]
        with self.assertRaisesRegex(ValueError,'closed_history_unresolved'):self.auth.prior()
        self.node.rows[0]['htlcs']=[]
        closed=copy.deepcopy(self.node.rows.pop())
        closed.update(leased=False,funding_withheld=False,closer='remote',last_commitment_txid='ab'*32)
        call=self.auth.rpc
        def rpc(method,**params):
            return {'closedchannels':[closed]} if method=='listclosedchannels' else call(method,**params)
        with patch.object(self.auth,'rpc',side_effect=rpc):
            self.auth.prior()
            closed['funding_txid']='cd'*32
            with self.assertRaisesRegex(ValueError,'closed_funding_changed'):self.auth.prior()

    def test_add_ready_channel_without_liquidity_or_disconnect_churn(self):
        self.node.rows[0].update(spendable_msat=20000000000,receivable_msat=20000000000)
        self.trust.maintain();old=copy.deepcopy(self.auth.record['current']);self.extra_channel()
        self.trust.maintain();current=copy.deepcopy(self.auth.record['current'])
        self.assertNotEqual(old,current)
        for gid in current.values():self.assertEqual(len(self.auth.record['grants'][gid]['terms']['channels']),2)
        self.node.rows[1]['peer_connected']=False
        self.trust.maintain();self.node.rows[1]['peer_connected']=True
        self.node.rows[1]['spendable_msat']=0;self.node.rows[1]['receivable_msat']=0
        self.trust.maintain();self.assertEqual(current,self.auth.record['current'])
    def test_topology_change_preserves_unfinished_and_manual_grants(self):
        manual=self.review();self.confirm(manual);self.trust.maintain()
        self.extra_channel();self.auth.record['entries']['pending-fixture']={}
        before=copy.deepcopy(self.auth.record['current'])
        self.assertEqual(self.trust.maintain()['state'],'waiting_for_recovery')
        self.assertEqual(before,self.auth.record['current'])
        self.auth.record['entries'].pop('pending-fixture');self.trust.maintain()
        self.assertEqual(manual,self.auth.record['current']['outgoing'])

    def test_terminal_receipt_requires_confirmed_splice_lineage_before_renewal(self):
        self.trust.maintain();gid=self.auth.record['current']['outgoing']
        data=self.node.plan();self.node.plan_value=data
        eid=self.auth.enroll(gid,data,confirmed=True);self.auth.send(eid)
        self.node.finish();self.auth.reconcile(eid)
        receipt=copy.deepcopy(self.auth.record['entries'][eid]);old=copy.deepcopy(data['channel'])
        row=self.node.rows[0];row.update(funding_txid='ee'*32,short_channel_id='121x2x0',funding_outnum=0)
        tx=dict(hash=row['funding_txid'],blockheight=121,txindex=2,outputs=[dict(index=0)],
                inputs=[dict(txid=old['funding_txid'],index=old['funding_outnum'])])
        call=self.auth.rpc
        def rpc(method,**params):
            return {'transactions':[tx]} if method=='listtransactions' else call(method,**params)
        with patch.object(self.auth,'rpc',side_effect=rpc):
            self.auth.prior()
            tx['blockheight']=0
            with self.assertRaisesRegex(ValueError,'splice_unconfirmed'):self.auth.prior()
            tx['blockheight']=121;tx['inputs'][0]['txid']='ff'*32
            with self.assertRaisesRegex(ValueError,'splice_funding_unproven'):self.auth.prior()
            tx['inputs'][0]['txid']=old['funding_txid']
            row['peer_id']='02'+'ff'*32
            with self.assertRaisesRegex(ValueError,'splice_identity_changed'):self.auth.prior()
            row['peer_id']=old['peer_id']
            self.trust.maintain()
            self.assertNotEqual(gid,self.auth.record['current']['outgoing'])
        self.assertEqual(receipt,self.auth.record['entries'][eid])

    def test_splice_refreshes_funding_pins_once_and_keeps_old_grants(self):
        self.xbt_liquidity();self.trust.maintain()
        old=copy.deepcopy(self.auth.record['current'])
        originals={gid:copy.deepcopy(self.auth.record['grants'][gid]) for gid in old.values()}
        row=self.node.rows[0];row.update(funding_txid='ee'*32,short_channel_id='121x2x0')
        self.trust.maintain();current=copy.deepcopy(self.auth.record['current'])
        for kind in ba.KINDS:
            self.assertNotEqual(old[kind],current[kind])
            pin=self.auth.record['grants'][current[kind]]['terms']['channels'][0]
            self.assertEqual(pin['funding_txid'],row['funding_txid'])
            self.assertEqual(pin['short_channel_id'],row['short_channel_id'])
            self.assertEqual(originals[old[kind]],self.auth.record['grants'][old[kind]])
        self.trust.maintain();self.assertEqual(current,self.auth.record['current'])

    def test_splice_refresh_waits_for_recovery_and_eligible_channel(self):
        self.xbt_liquidity();self.trust.maintain();old=copy.deepcopy(self.auth.record['current'])
        self.node.rows[0].update(funding_txid='ee'*32,short_channel_id='121x2x0',peer_connected=False)
        self.trust.maintain();self.assertEqual(old,self.auth.record['current'])
        self.node.rows[0]['peer_connected']=True
        self.auth.record['entries']['pending-fixture']={}
        self.assertEqual(self.trust.maintain()['state'],'waiting_for_recovery')
        self.assertEqual(old,self.auth.record['current'])
        self.auth.record['entries'].pop('pending-fixture');self.trust.maintain()
        self.assertNotEqual(old,self.auth.record['current'])

    def test_chain_specific_ceiling_and_liquidity(self):
        self.node.rows[0].update(spendable_msat=20000000000,receivable_msat=20000000000)
        self.trust.maintain()
        self.assertTrue(all(v['terms']['limits']['max_amount_msat']==100000000 for v in self.auth.record['grants'].values()))
        self.xbt_liquidity();self.node.rows[0]['receivable_msat']=500252000
        self.trust.maintain()
        def current(kind):return self.auth.record['grants'][self.auth.record['current'][kind]]['terms']['limits']
        self.assertEqual(current('outgoing')['max_amount_msat'],10000000000)
        self.assertEqual(current('outgoing')['total_amount_msat'],30000000000)
        self.assertEqual(current('incoming')['max_amount_msat'],500252000)
    def test_liquidity_limited_grant_promotes_once_at_policy_cap(self):
        self.xbt_liquidity();self.node.rows[0]['receivable_msat']=500252000
        self.trust.maintain();old=copy.deepcopy(self.auth.record['current'])
        self.node.rows[0]['receivable_msat']=600000000
        self.trust.maintain();self.assertEqual(old,self.auth.record['current'])
        self.node.rows[0]['receivable_msat']=17384650000
        self.auth.record['entries']['pending-fixture']={}
        self.assertEqual(self.trust.maintain()['state'],'waiting_for_recovery')
        self.assertEqual(old,self.auth.record['current'])
        self.auth.record['entries'].pop('pending-fixture')
        self.trust.maintain();new=copy.deepcopy(self.auth.record['current'])
        self.assertNotEqual(old['incoming'],new['incoming'])
        self.assertEqual(old['outgoing'],new['outgoing'])
        self.assertEqual(self.auth.record['grants'][new['incoming']]['terms']['limits']['max_amount_msat'],10000000000)
        self.assertEqual(self.auth.record['grants'][old['incoming']]['terms']['limits']['max_amount_msat'],500252000)
        self.node.rows[0]['receivable_msat']=400000000
        self.trust.maintain();self.node.rows[0]['receivable_msat']=20000000000
        self.trust.maintain();self.assertEqual(new,self.auth.record['current'])
        self.assertEqual(len(self.auth.record['grants']),3)

    def test_old_managed_xbt_grants_refresh_once_with_recovery_guard(self):
        self.xbt_liquidity()
        with patch.dict(lt.PER_SWAP_MSAT,{ci.PRIVKEYIO_XBT:10000000}):self.trust.maintain()
        old=copy.deepcopy(self.auth.record['current'])
        self.auth.record['entries']['pending-fixture']={}
        self.assertEqual(self.trust.maintain()['state'],'waiting_for_recovery')
        self.assertEqual(old,self.auth.record['current'])
        self.auth.record['entries'].pop('pending-fixture')
        self.trust.maintain();new=copy.deepcopy(self.auth.record['current'])
        self.assertTrue(all(old[k]!=new[k] for k in ba.KINDS))
        self.assertEqual(len(self.auth.record['grants']),4)
        self.open();self.trust.maintain()
        self.assertEqual(new,self.auth.record['current']);self.assertEqual(len(self.auth.record['grants']),4)
    def test_policy_upgrade_does_not_override_manual_or_paused_xbt_grants(self):
        self.xbt_liquidity();manual=self.review();self.confirm(manual)
        self.trust.maintain();self.assertEqual(self.auth.record['current']['outgoing'],manual)
        self.auth.pause(self.auth.record['current']['incoming'])
        self.assertFalse(self.trust.maintain()['enabled'])
        self.assertEqual(self.auth.record['current']['outgoing'],manual)
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
    def test_idle_owned_delay_budget_upgrades_once(self):
        original=self.trust.plan
        def old_plan(kind):
            g=original(kind)
            if g and kind=='outgoing':g['limits']['max_delay_blocks']=288
            return g
        with patch.object(self.trust,'plan',side_effect=old_plan):self.trust.maintain()
        previous=copy.deepcopy(self.auth.record['current'])
        self.trust.maintain()
        current=copy.deepcopy(self.auth.record['current'])
        self.assertEqual(current['incoming'],previous['incoming'])
        self.assertNotEqual(current['outgoing'],previous['outgoing'])
        self.assertEqual(self.auth.record['grants'][current['outgoing']]['terms']['limits']['max_delay_blocks'],576)
        self.assertEqual(self.auth.record['grants'][previous['outgoing']]['terms']['limits']['max_delay_blocks'],288)
        self.trust.maintain();self.assertEqual(current,self.auth.record['current'])

    def test_old_manual_delay_budget_is_not_widened(self):
        gid=self.review();self.confirm(gid)
        self.trust.maintain()
        self.assertEqual(self.auth.record['current']['outgoing'],gid)
        self.assertEqual(self.auth.record['grants'][gid]['terms']['limits']['max_delay_blocks'],288)

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
