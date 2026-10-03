import importlib.util
import json
from pathlib import Path
import shutil
import sqlite3
from contextlib import closing
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('empty_backup', Path(__file__).resolve().parents[1] / 'assets/xbt/empty_backup.py')
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)


class EmptyBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'wallet'
        (self.root / 'xbt').mkdir(parents=True)
        (self.root / b.KEY).write_bytes(b'fixture key - not a real wallet')
        (self.root / b.SCB).write_bytes(b'fixture empty recovery file')
        self.node = bytes.fromhex('02' + '12' * 32)
        with closing(sqlite3.connect(self.root / b.DB)) as con, con:
            con.execute('CREATE TABLE vars (name TEXT, blobval BLOB)')
            con.executemany('INSERT INTO vars VALUES (?,?)', [('genesis_hash', b.CHAIN), ('node_id', self.node)])
            for t in b.TABLES:
                con.execute('CREATE TABLE ' + t + ' (id INTEGER)')

    def snapshot(self):
        b.capture(self.root)
        dest = Path(self.temp.name) / 'restored'
        shutil.copytree(self.root, dest)
        (dest / b.DB).unlink()
        return dest

    def test_empty_restore_preserves_files_and_expected_identity(self):
        dest = self.snapshot()
        b.restore(dest)
        b.restore(dest)  # interrupted init can repeat before startup
        self.assertFalse((dest / b.MARKER).exists())
        self.assertFalse((dest / b.DB).exists())
        self.assertEqual((dest / b.KEY).read_bytes(), (self.root / b.KEY).read_bytes())
        self.assertEqual(json.loads((dest / 'restored-identity.json').read_text())['node_id'], self.node.hex())
        self.assertEqual((dest / b.RECEIPT).stat().st_mode & 0o777, 0o600)

    def test_each_activity_table_refuses_and_invalidates_old_receipt(self):
        for table in b.TABLES:
            b.capture(self.root)
            with closing(sqlite3.connect(self.root / b.DB)) as con, con:
                con.execute('INSERT INTO ' + table + ' VALUES (1)')
            with self.assertRaises(ValueError):
                b.capture(self.root)
            self.assertFalse((self.root / b.RECEIPT).exists())
            with closing(sqlite3.connect(self.root / b.DB)) as con, con:
                con.execute('DELETE FROM ' + table)

    def test_wrong_chain_refused(self):
        with closing(sqlite3.connect(self.root / b.DB)) as con, con:
            con.execute("UPDATE vars SET blobval=? WHERE name='genesis_hash'", (bytes(32),))
        with self.assertRaises(ValueError):
            b.capture(self.root)

    def test_missing_schema_refused(self):
        with closing(sqlite3.connect(self.root / b.DB)) as con, con:
            con.execute('DROP TABLE outputs')
        with self.assertRaises(sqlite3.Error):
            b.capture(self.root)

    def test_live_wal_refused(self):
        (self.root / (b.DB + '-wal')).write_bytes(b'not checkpointed')
        with self.assertRaises(ValueError):
            b.capture(self.root)

    def test_restore_existing_database_preserved_and_blocked(self):
        b.capture(self.root)
        original = (self.root / b.DB).read_bytes()
        with self.assertRaises(ValueError):
            b.restore(self.root)
        self.assertEqual((self.root / b.DB).read_bytes(), original)
        self.assertTrue((self.root / b.MARKER).exists())

    def test_changed_key_or_scb_stays_blocked(self):
        dest = self.snapshot()
        for name in (b.KEY, b.SCB):
            before = (dest / name).read_bytes()
            (dest / name).write_bytes(b'changed')
            with self.assertRaises(ValueError):
                b.restore(dest)
            self.assertTrue((dest / b.MARKER).exists())
            (dest / name).write_bytes(before)

    def test_old_backup_without_receipt_blocked(self):
        dest = self.snapshot()
        (dest / b.RECEIPT).unlink()
        with self.assertRaises(FileNotFoundError):
            b.restore(dest)
        self.assertTrue((dest / b.MARKER).exists())

    def test_symlinked_secret_refused(self):
        original = self.root / 'other-key'
        (self.root / b.KEY).rename(original)
        (self.root / b.KEY).symlink_to(original)
        with self.assertRaises(ValueError):
            b.capture(self.root)


if __name__ == '__main__':
    unittest.main()
