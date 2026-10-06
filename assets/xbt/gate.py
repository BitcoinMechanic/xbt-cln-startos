#!/usr/bin/env python3
"""Explicit XBT gate opt-in. Never publishes invoices or submits payments."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import stat
import subprocess
import sys
import fcntl
from coordinator import SOURCE as PIN, Preparation
from controller_credential import Blocked, load, require, save

PROFILE = 'reverse-live-v1'
PLUGIN = '/usr/local/libexec/xbt-gate-plugin'
SOURCE = Path('/usr/local/libexec/xbt-swap')
SOURCE_HASH = '071029c6e1b1b4100499f9a1400a524828fbb48d1013dddd5e7c299f0449d449'
RECORD = 'xbt-gate-activation.json'
BARRIER = 'xbt-gate-restored.json'


def regular(path):
    require(stat.S_ISREG(path.lstat().st_mode), 'nonregular_file')
    return path.read_bytes()


def key_hash(root):
    require(not root.is_symlink() and not (root / 'xbt').is_symlink(), 'invalid_root')
    secret = regular(root / 'xbt/hsm_secret')
    require(bool(secret), 'empty_secret')
    return hashlib.sha256(secret).hexdigest()


def source_check(source=SOURCE):
    require(source.is_dir() and not source.is_symlink(), 'invalid_source_directory')
    digest = hashlib.sha256()
    for path in sorted(source.rglob('*.py')):
        digest.update(path.relative_to(source).as_posix().encode() + b'\0' + hashlib.sha256(regular(path)).digest())
    require(digest.hexdigest() == SOURCE_HASH, 'gate_source_changed')


def record(root):
    require(not os.path.lexists(root / BARRIER), 'restored_gate_blocked')
    require(not os.path.lexists(root / 'restore-blocked') and not os.path.lexists(root / 'bitcoin'), 'wallet_recovery_blocked')
    if os.path.lexists(root / 'recovery-intent.json'):
        require(load(root / 'recovery-intent.json').get('phase') == 'finished-empty', 'wallet_recovery_active')
    data = load(root / RECORD)
    require(set(data) == {'schema', 'profile', 'source_commit', 'source_sha256', 'node_id', 'secret_sha256'}, 'activation_invalid')
    require(data['schema'] == 1 and data['profile'] == PROFILE and data['source_commit'] == PIN
            and data['source_sha256'] == SOURCE_HASH and data['secret_sha256'] == key_hash(root), 'activation_binding_changed')
    return data


def journal_path(root):
    directory = root / 'xbt/swap-gate'
    require(not directory.is_symlink(), 'invalid_gate_directory')
    path = directory / 'reverse_gate.quotes.json'
    if os.path.lexists(path): regular(path)
    return path


class Gate:
    def __init__(self, root, rpc=None, preparation=None):
        self.root = Path(root)
        self.rpc = rpc or self.call
        self.preparation = preparation or Preparation(root, 'xbt')

    def call(self, method):
        require(method in ('getinfo', 'listpeerchannels', 'plugin', 'reverse-pilot-info'), 'unexpected_rpc')
        args = ['list'] if method == 'plugin' else []
        result = subprocess.run(['lightning-cli', '--lightning-dir='+str(self.root), '--network=xbt',
                                 '--json', '--notifications=none', method, *args], capture_output=True, text=True, timeout=30)
        require(result.returncode == 0, 'gate_rpc_unavailable')
        value = json.loads(result.stdout)
        require(isinstance(value, dict) and 'error' not in value, 'gate_rpc_unavailable')
        return value

    def status(self):
        configured = os.path.lexists(self.root / RECORD)
        blocked = os.path.lexists(self.root / BARRIER)
        info = self.rpc('getinfo')
        require(info.get('network') == 'xbt', 'wrong_network')
        if configured:
            binding = record(self.root)
            require(binding['node_id'] == info.get('id'), 'node_identity_changed')
        plugins = self.rpc('plugin').get('plugins')
        require(isinstance(plugins, list), 'invalid_plugin_status')
        active = any(p.get('name') == PLUGIN and p.get('active') is True for p in plugins)
        count = 0
        if active:
            require(configured and not blocked, 'unbound_active_gate')
            result = self.rpc('reverse-pilot-info')
            require(result.get('profile') == PROFILE, 'gate_profile_changed')
            require(result.get('gate_active') is True, 'gate_inactive')
            path = journal_path(self.root)
            if os.path.lexists(path):
                quotes = load(path)
                require(isinstance(quotes, dict), 'invalid_gate_journal')
                count = len(quotes)
        return dict(configured=configured, active=active, restart_required=configured and not active,
                    restored_gate_blocked=blocked, profile=PROFILE, registered_quotes=count,
                    btc_sats=1500, max_xbt_sats=500000, max_routing_fee_sats=30, one_active_quote_only=True,
                    controller_live_execution_enabled=False, payment_started=False)

    def activate(self, confirmed):
        require(confirmed is True, 'confirmation_required')
        source_check()
        require(not os.path.lexists(self.root / BARRIER), 'restored_gate_blocked')
        expected, status = self.preparation.inspect()
        require(status['prepared'], 'prepare_coordinator_first')
        channels = self.rpc('listpeerchannels')['channels']
        require(not any(c.get('htlcs') for c in channels), 'pending_htlcs')
        require(any(c.get('state') == 'CHANNELD_NORMAL' and c.get('peer_connected') is True for c in channels), 'connected_channel_required')
        target = dict(schema=1, profile=PROFILE, source_commit=PIN, source_sha256=SOURCE_HASH,
                      node_id=expected['node_id'], secret_sha256=key_hash(self.root))
        if os.path.lexists(self.root / RECORD):
            require(record(self.root) == target, 'activation_binding_changed')
        else:
            journal = journal_path(self.root)
            require(not os.path.lexists(journal), 'existing_gate_journal_requires_recovery')
            save(self.root / RECORD, target)
        return self.status()


def launch(root, args):
    require(args and args[0] == 'lightningd', 'invalid_launch')
    require(not any('xbt-live-pilot' in a or 'reverse-live' in a or 'xbt-gate-plugin' in a for a in args), 'duplicate_gate_option')
    if os.path.lexists(root / RECORD):
        source_check()
        record(root)
        path = journal_path(root)
        path.parent.mkdir(mode=0o700, exist_ok=True)
        os.environ['XBT_GATE_ROOT'] = str(root)
        args += ['--plugin='+PLUGIN]
    os.execvp(args[0], args)


def plugin():
    root = Path(os.environ['XBT_GATE_ROOT'])
    source_check()
    record(root)
    path = journal_path(root)
    lock_fd = os.open(path.parent / 'gate.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    require(stat.S_ISREG(os.fstat(lock_fd).st_mode), 'invalid_gate_lock')
    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    # All imported code is hash-checked in the immutable image. The volume holds only JSON.
    sys.path.insert(0, str(SOURCE))
    original = sys.stdin
    token = None
    try:
        namespace = runpy.run_path(str(SOURCE / 'reverse_gate.py'))
        from reverse_activation import ACTIVE
        # This private context enables only this gate process after validating the
        # package's explicit identity-bound opt-in. No controller process inherits it.
        token = ACTIVE.set(True)
        def requests():
            for line in original:
                if line.strip():
                    message = json.loads(line)
                    if message.get('method') == 'init':
                        require(message['params']['configuration']['network'] == 'xbt', 'wrong_network')
                yield line
        sys.stdin = requests()
        namespace['main'](path, live=True)
    finally:
        if token is not None: ACTIVE.reset(token)
        sys.stdin = original
        sys.path.pop(0)
        os.close(lock_fd)


def main():
    os.umask(0o077)
    try:
        operation = sys.argv[1]
        if operation == 'plugin': plugin(); return
        root = Path(sys.argv[2])
        if operation == 'launch': launch(root, sys.argv[3:]); return
        require(operation in ('status', 'activate'), 'unknown_operation')
        if operation == 'status': result = Gate(root).status()
        else:
            request = json.load(sys.stdin)
            fd = os.open(root / 'xbt-gate.lock', os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'a') as lock:
                require(stat.S_ISREG(os.fstat(lock.fileno()).st_mode), 'invalid_lock')
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = Gate(root).activate(request.get('confirmed'))
        print(json.dumps(result))
    except Exception as error:
        # Plugin stdout is a protocol stream; never put action JSON on it.
        if len(sys.argv) > 1 and sys.argv[1] == 'plugin': raise SystemExit(1)
        print(json.dumps(dict(error='XBT gate operation blocked.', reason=str(error) if isinstance(error, Blocked) else 'private_details_withheld')))
        raise SystemExit(1)


if __name__ == '__main__': main()
