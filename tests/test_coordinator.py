import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'assets/xbt'))
from coordinator import Preparation, SOURCE, RECORD


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bundle = self.root / 'bundle'
        self.bundle.mkdir()
        (self.bundle / 'SOURCE_COMMIT').write_text(SOURCE)
        for name in ('reverse_gate.py', 'quote_plugin.py', 'reverse_activation.py'):
            (self.bundle / name).touch()
        self.info = {'network': 'xbt', 'id': '02' + 'a' * 64}
        self.channels = []
        self.calls = []
        self.worker = Preparation(self.root, rpc=self.rpc)

    def rpc(self, method, **kwargs):
        self.calls.append(method)
        if method == 'getinfo':
            return self.info
        if method == 'listpeerchannels':
            return {'channels': self.channels}
        self.fail('Mutating or unexpected RPC: ' + method)

    def test_inspection_creates_no_receipt(self):
        self.assertFalse(self.worker.inspect(self.bundle)[1]['prepared'])
        self.assertFalse((self.root / RECORD).exists())

    def test_confirmation_required_before_rpc(self):
        with self.assertRaises(ValueError):
            self.worker.prepare(False, self.bundle)
        self.assertEqual(self.calls, [])

    def test_prepare_repeat_preserves_receipt(self):
        result = self.worker.prepare(True, self.bundle)
        path = self.root / RECORD
        before = (path.read_bytes(), path.stat().st_mtime_ns)
        self.assertTrue(result['prepared'])
        self.assertFalse(result['live_activation_enabled_by_package'])
        self.worker.prepare(True, self.bundle)
        self.assertEqual(before, (path.read_bytes(), path.stat().st_mtime_ns))
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_changed_identity_preserves_receipt(self):
        self.worker.prepare(True, self.bundle)
        before = (self.root / RECORD).read_bytes()
        self.info['id'] = '03' + 'b' * 64
        with self.assertRaises(ValueError):
            self.worker.prepare(True, self.bundle)
        self.assertEqual(before, (self.root / RECORD).read_bytes())

    def test_warning_network_pending_refused(self):
        for case in ('warning', 'network', 'pending'):
            with self.subTest(case=case):
                self.info = {'network': 'xbt', 'id': '02' + 'a' * 64}
                self.channels = []
                if case == 'warning': self.info['warning_lightningd_sync'] = 'sync'
                if case == 'network': self.info['network'] = 'bitcoin'
                if case == 'pending': self.channels = [{'htlcs': [{}]}]
                with self.assertRaises(ValueError): self.worker.prepare(True, self.bundle)
                self.assertFalse((self.root / RECORD).exists())

    def test_restore_block_refused(self):
        (self.root / 'restore-blocked').touch()
        with self.assertRaises(ValueError): self.worker.prepare(True, self.bundle)
        self.assertEqual(self.calls, [])

    def test_wrong_revision_refused_before_rpc(self):
        (self.bundle / 'SOURCE_COMMIT').write_text('wrong')
        with self.assertRaises(ValueError): self.worker.prepare(True, self.bundle)
        self.assertEqual(self.calls, [])

    def test_missing_module_refused(self):
        (self.bundle / 'reverse_gate.py').unlink()
        with self.assertRaises(ValueError): self.worker.prepare(True, self.bundle)

    def test_symlink_receipt_refused(self):
        (self.root / RECORD).symlink_to(self.bundle / 'SOURCE_COMMIT')
        with self.assertRaises((ValueError, RuntimeError)): self.worker.prepare(True, self.bundle)


if __name__ == '__main__': unittest.main()
