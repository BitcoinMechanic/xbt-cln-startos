import hashlib
import json
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
import recovery as r


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'wallet'
        (self.root / 'xbt').mkdir(parents=True)
        self.db, self.key, self.scb, chain = r.layout('xbt')
        (self.root / self.key).write_bytes(b'fixture key')
        (self.root / self.scb).write_bytes(b'fixture scb')
        self.node = '02' + '12'*32
        self.cid = '34'*32
        with closing(sqlite3.connect(self.root / self.db)) as con, con:
            con.executescript('''
                CREATE TABLE vars(name TEXT, blobval BLOB, intval INTEGER);
                CREATE TABLE channels(full_channel_id BLOB, state INTEGER);
                CREATE TABLE channel_htlcs(hstate INTEGER);
                CREATE TABLE channel_funding_inflights(id INTEGER);
                CREATE TABLE outputs(status INTEGER, confirmation_height INTEGER);
            ''')
            con.executemany('INSERT INTO vars VALUES(?,?,?)', [
                ('genesis_hash', chain, None), ('node_id', bytes.fromhex(self.node), None),
                ('bip32_max_index', None, 1), ('bip86_max_index', None, 1)])
            con.execute('INSERT INTO channels VALUES(?,3)', (bytes.fromhex(self.cid),))
            con.execute('INSERT INTO channel_htlcs VALUES(9)')
        self.calls = []
        self.channels = []
        self.lost = False

    def restored(self):
        r.capture(self.root)
        dest = Path(self.tmp.name) / 'restored'
        shutil.copytree(self.root, dest)
        (dest / self.db).unlink()
        r.restore(dest)
        return dest

    def rpc(self, method):
        self.calls.append(method)
        if method == 'getinfo':
            return {'network': 'xbt', 'id': self.node}
        if method == 'listpeerchannels':
            return {'channels': self.channels}
        if method == 'getemergencyrecoverdata':
            return {'backed_up_channel_ids': [self.cid], 'filedata': b'fixture scb'.hex()}
        if method == 'emergencyrecover':
            self.channels = [{'channel_id': self.cid, 'state': 'AWAITING_UNILATERAL'}]
            if self.lost:
                raise RuntimeError('lost reply')
            return {'stubs': [self.cid]}
        raise AssertionError(method)

    def test_import_and_repeat_never_claim_completion(self):
        dest = self.restored()
        for _ in range(2):
            result = r.step(dest, rpc=self.rpc)
            self.assertFalse(result['complete'])
            self.assertEqual(result['waiting_for_close'], 1)
        self.assertEqual(self.calls.count('emergencyrecover'), 1)
        self.channels[0]['state'] = 'ONCHAIN'
        self.assertEqual(r.step(dest, rpc=self.rpc)['onchain_channels'], 1)
        self.channels = []
        self.assertFalse(r.step(dest, rpc=self.rpc)['complete'])
        self.assertEqual(self.calls.count('emergencyrecover'), 1)

    def test_lost_import_reply_reconciles_channel_without_second_import(self):
        dest = self.restored()
        self.lost = True
        with self.assertRaises(RuntimeError):
            r.step(dest, rpc=self.rpc)
        self.assertEqual(r.load(dest, r.INTENT)['phase'], 'importing')
        r.step(dest, rpc=self.rpc)
        self.assertEqual(self.calls.count('emergencyrecover'), 1)

    def test_wrong_identity_blocks_all_mutations(self):
        dest = self.restored()
        self.node = '03' + '56'*32
        with self.assertRaises(ValueError):
            r.step(dest, rpc=self.rpc)
        self.assertNotIn('emergencyrecover', self.calls)

    def test_wrong_or_missing_backup_channel_blocks_import(self):
        dest = self.restored()
        self.cid = '78'*32
        with self.assertRaises(ValueError):
            r.step(dest, rpc=self.rpc)
        self.assertNotIn('emergencyrecover', self.calls)

    def test_changed_backup_bytes_block_import(self):
        dest = self.restored()
        def rpc(method):
            data = self.rpc(method)
            if method == 'getemergencyrecoverdata':
                data['filedata'] = b'changed'.hex()
            return data
        with self.assertRaises(ValueError):
            r.step(dest, rpc=rpc)
        self.assertNotIn('emergencyrecover', self.calls)

    def test_sync_warning_defers_import(self):
        dest = self.restored()
        def rpc(method):
            data = self.rpc(method)
            if method == 'getinfo':
                data['warning_bitcoind_sync'] = 'syncing'
            return data
        self.assertEqual(r.step(dest, rpc=rpc)['phase'], 'scanning')
        self.assertEqual(self.calls, ['getinfo'])

    def test_pending_htlc_non_normal_channel_inflight_and_key_limit_refused(self):
        cases = [
            ('INSERT INTO channel_htlcs VALUES(4)', 'DELETE FROM channel_htlcs WHERE hstate=4'),
            ('UPDATE channels SET state=9', 'UPDATE channels SET state=3'),
            ('INSERT INTO channel_funding_inflights VALUES(1)', 'DELETE FROM channel_funding_inflights'),
            ("UPDATE vars SET intval=51 WHERE name='bip86_max_index'", "UPDATE vars SET intval=1 WHERE name='bip86_max_index'"),
            ('INSERT INTO outputs VALUES(1,100)', 'DELETE FROM outputs'),
            ('INSERT INTO outputs VALUES(0,NULL)', 'DELETE FROM outputs'),
        ]
        for change, undo in cases:
            with self.subTest(change=change):
                r.capture(self.root)
                with closing(sqlite3.connect(self.root / self.db)) as con, con:
                    con.execute(change)
                with self.assertRaises(ValueError):
                    r.capture(self.root)
                self.assertFalse((self.root / r.RECEIPT).exists())
                with closing(sqlite3.connect(self.root / self.db)) as con, con:
                    con.execute(undo)

    def test_existing_database_preserved_and_restore_blocked(self):
        r.capture(self.root)
        before = (self.root / self.db).read_bytes()
        with self.assertRaises(ValueError):
            r.restore(self.root)
        self.assertEqual((self.root / self.db).read_bytes(), before)
        self.assertTrue((self.root / 'restore-blocked').exists())

    def test_changed_key_blocks_restore(self):
        dest = self.restored()
        (dest / self.key).write_bytes(b'wrong')
        with self.assertRaises(ValueError):
            r.restore(dest)
        self.assertTrue((dest / 'restore-blocked').exists())

    def test_wrong_chain_and_backup_during_recovery_refused(self):
        dest = self.restored()
        with self.assertRaises(ValueError):
            r.capture(dest)
        with closing(sqlite3.connect(self.root / self.db)) as con, con:
            con.execute("UPDATE vars SET blobval=? WHERE name='genesis_hash'", (bytes(32),))
        with self.assertRaises(ValueError):
            r.capture(self.root)

    def test_birth_record_only_for_new_wallet_and_keeps_earliest_height(self):
        r.record_birth(self.root, 1000)
        self.assertFalse((self.root / r.BIRTH).exists())  # existing key
        fresh = Path(self.tmp.name) / 'fresh'
        fresh.mkdir()
        r.record_birth(fresh, 1000)
        r.record_birth(fresh, 2000)
        self.assertEqual(r.load(fresh, r.BIRTH)['scan_start'], 856)
        shutil.copyfile(fresh / r.BIRTH, self.root / r.BIRTH)
        r.capture(self.root)
        self.assertEqual(r.load(self.root, r.RECEIPT)['scan_start'], 856)

    def test_empty_scan_adjustment_preserves_database(self):
        with closing(sqlite3.connect(self.root / self.db)) as con, con:
            con.execute('DELETE FROM channels')
            con.execute('DELETE FROM channel_htlcs')
            for table in ('transactions', 'payments', 'invoices'):
                con.execute('CREATE TABLE ' + table + '(id INTEGER)')
        dest = self.restored()
        shutil.copyfile(self.root / self.db, dest / self.db)
        before = (dest / self.db).read_bytes()
        with self.assertRaises(ValueError):
            r.set_empty_scan_start(dest, 974000, False)
        r.set_empty_scan_start(dest, 974000, True)
        self.assertEqual((dest / self.db).read_bytes(), before)
        self.assertEqual(r.load(dest, r.INTENT)['scan_start'], 974000)
        for table in ('outputs', 'transactions', 'payments', 'invoices'):
            with self.subTest(table=table):
                with closing(sqlite3.connect(dest / self.db)) as con, con:
                    if table == 'outputs':
                        con.execute('INSERT INTO outputs VALUES(0,100)')
                    else:
                        con.execute('INSERT INTO ' + table + ' VALUES(1)')
                with self.assertRaises(ValueError):
                    r.set_empty_scan_start(dest, 975000, True)
                self.assertEqual(r.load(dest, r.INTENT)['scan_start'], 974000)
                with closing(sqlite3.connect(dest / self.db)) as con, con:
                    con.execute('DELETE FROM ' + table)

    def test_scan_adjustment_refuses_channels_or_imported_phase(self):
        dest = self.restored()
        with self.assertRaises(ValueError):
            r.set_empty_scan_start(dest, 90, True)
        state = r.load(dest, r.INTENT)
        r.atomic_json(dest, r.INTENT, {**state, 'channels': [], 'phase': 'imported'})
        with self.assertRaises(ValueError):
            r.set_empty_scan_start(dest, 90, True)

    def test_invalid_scan_heights_refused(self):
        for value in (0, -1, True, 1.5, '90', 2147483648):
            with self.subTest(value=value), self.assertRaises(ValueError):
                r.valid_height(value)

    def empty_monitoring(self):
        with closing(sqlite3.connect(self.root / self.db)) as con, con:
            con.execute('DELETE FROM channels')
            con.execute('DELETE FROM channel_htlcs')
            for table in ('transactions', 'payments', 'invoices'):
                con.execute('CREATE TABLE ' + table + '(id INTEGER)')
        dest = self.restored()
        shutil.copyfile(self.root / self.db, dest / self.db)
        r.set_empty_scan_start(dest, 900, True)
        status = r.step(dest, rpc=self.rpc)
        r.atomic_json(dest, r.STATUS, {**status, 'checked_at': r.time.time()})
        return dest

    def test_finish_preserves_database_audit_and_allows_backup(self):
        dest = self.empty_monitoring()
        before = (dest / self.db).read_bytes()
        r.finish_empty(dest, True)
        intent = (dest / r.INTENT).read_bytes()
        r.finish_empty(dest, True)
        self.assertEqual((dest / r.INTENT).read_bytes(), intent)
        self.assertEqual((dest / self.db).read_bytes(), before)
        self.assertEqual(r.load(dest, r.INTENT)['phase'], 'finished-empty')
        r.capture(dest)
        self.assertEqual(r.load(dest, r.RECEIPT)['scan_start'], 900)

    def test_finish_requires_confirmation_fresh_monitoring_and_stopped_worker(self):
        dest = self.empty_monitoring()
        with self.assertRaises(ValueError):
            r.finish_empty(dest, False)
        status = r.load(dest, r.STATUS)
        for change in ({'checked_at': 1}, {'phase': 'scanning'}, {'expected_channels': 1}):
            r.atomic_json(dest, r.STATUS, {**status, **change})
            with self.assertRaises(ValueError):
                r.finish_empty(dest, True)
        r.atomic_json(dest, r.STATUS, status)
        with (dest / 'recovery.lock').open('a') as lock:
            r.fcntl.flock(lock, r.fcntl.LOCK_EX | r.fcntl.LOCK_NB)
            with self.assertRaises(BlockingIOError):
                r.finish_empty(dest, True)
        self.assertEqual(r.load(dest, r.INTENT)['phase'], 'imported')

    def test_finish_refuses_recorded_activity_and_changed_key(self):
        dest = self.empty_monitoring()
        for table in ('channels', 'channel_htlcs', 'outputs', 'transactions', 'payments', 'invoices'):
            with self.subTest(table=table):
                with closing(sqlite3.connect(dest / self.db)) as con, con:
                    con.execute('INSERT INTO ' + table + ' DEFAULT VALUES')
                with self.assertRaises(ValueError):
                    r.finish_empty(dest, True)
                with closing(sqlite3.connect(dest / self.db)) as con, con:
                    con.execute('DELETE FROM ' + table)
        (dest / self.key).write_bytes(b'changed')
        with self.assertRaises(ValueError):
            r.finish_empty(dest, True)

    def test_mainnet_chain_constant_and_network_separation(self):
        self.assertEqual(r.layout('xbt')[3].hex(), '75c09f7ebd1363495bc336d1a47da2b43548be1e9b4403ee2db6d901154653e4')
        self.assertNotEqual(r.layout('xbt')[3], r.layout('xbt-regtest')[3])
        with self.assertRaises(ValueError):
            r.layout('bitcoin')


if __name__ == '__main__':
    unittest.main()
