#!/usr/bin/env python3
"""Offline, stopped-service backup checks for the unfunded observation release.

This is not funded-wallet recovery. A private receipt binds an empty database's
identity to its key and SCB; neither the database nor a live RPC socket is restored.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import sys
import tempfile

CHAIN = bytes.fromhex('75c09f7ebd1363495bc336d1a47da2b43548be1e9b4403ee2db6d901154653e4')
TABLES = ('channels', 'channel_htlcs', 'outputs', 'transactions', 'payments', 'invoices')
RECEIPT = 'empty-wallet-backup.json'
MARKER = 'restore-blocked'
DB = 'xbt/lightningd.sqlite3'
KEY = 'xbt/hsm_secret'
SCB = 'xbt/emergency.recover'


def regular(root, name):
    path = root / name
    # Refuse symlinks in both the final file and the network directory.
    for parent in path.parents:
        if parent == root:
            break
        if parent.is_symlink():
            raise ValueError('Symlinked wallet directory refused')
    if not stat.S_ISREG(path.lstat().st_mode):
        raise ValueError('Expected a regular wallet file')
    return path


def digest(root, name):
    p = regular(root, name)
    if not 0 < p.stat().st_size <= 1024 * 1024:
        raise ValueError('Invalid wallet file size')
    return hashlib.sha256(p.read_bytes()).hexdigest()


def atomic_json(root, name, data):
    fd, temp = tempfile.mkstemp(prefix='.backup-', dir=root)
    try:
        with os.fdopen(fd, 'w') as f:
            json.dump(data, f)
            f.write('\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, root / name)
        fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        Path(temp).unlink(missing_ok=True)


def capture(root):
    # Invalidate any previous receipt before inspecting this backup generation.
    (root / RECEIPT).unlink(missing_ok=True)
    if (root / MARKER).exists() or (root / 'bitcoin').exists():
        raise ValueError('Blocked restore or Bitcoin wallet detected')
    db = regular(root, DB)
    wal = root / (DB + '-wal')
    if wal.exists() and wal.stat().st_size:
        raise ValueError('Wallet database is not checkpointed; backup refused')
    con = sqlite3.connect(db.as_uri() + '?mode=ro', uri=True)
    try:
        con.execute('PRAGMA query_only=ON')
        if con.execute('PRAGMA quick_check').fetchall() != [('ok',)]:
            raise ValueError('Wallet database check failed')
        if con.execute("SELECT blobval FROM vars WHERE name='genesis_hash'").fetchall() != [(CHAIN,)]:
            raise ValueError('Wallet is not the pinned XBT network')
        for table in TABLES:
            if con.execute('SELECT 1 FROM ' + table + ' LIMIT 1').fetchone():
                raise ValueError('Wallet has recorded activity; funded recovery is not enabled')
        rows = con.execute("SELECT blobval FROM vars WHERE name='node_id'").fetchall()
        if len(rows) != 1 or not isinstance(rows[0][0], bytes):
            raise ValueError('Missing wallet identity')
        node = rows[0][0].hex()
        if not re.fullmatch(r'0[23][0-9a-f]{64}', node):
            raise ValueError('Invalid wallet identity')
    finally:
        con.close()
    atomic_json(root, RECEIPT, {
        'schema': 1, 'scope': 'empty-xbt-wallet', 'node_id': node,
        'key_sha256': digest(root, KEY), 'scb_sha256': digest(root, SCB),
    })


def restore(root):
    # Written before validation and retained on every failure.
    atomic_json(root, MARKER, {'blocked': True})
    for name in (DB, DB + '-wal', DB + '-shm', 'bitcoin'):
        if os.path.lexists(root / name):
            raise ValueError('Restore requires a fresh volume without a wallet database')
    receipt_file = regular(root, RECEIPT)
    if receipt_file.stat().st_size > 4096:
        raise ValueError('Invalid backup receipt')
    receipt = json.loads(receipt_file.read_text())
    if (receipt.get('schema') != 1 or receipt.get('scope') != 'empty-xbt-wallet'
            or not re.fullmatch(r'0[23][0-9a-f]{64}', receipt.get('node_id', ''))
            or receipt.get('key_sha256') != digest(root, KEY)
            or receipt.get('scb_sha256') != digest(root, SCB)):
        raise ValueError('Backup identity or file binding failed')
    # Keep expected identity until the first successful RPC verifies it.
    atomic_json(root, 'restored-identity.json', {
        'schema': 1, 'node_id': receipt['node_id'],
    })
    (root / MARKER).unlink()


if __name__ == '__main__':
    try:
        mode, directory = sys.argv[1:]
        root = Path(directory).resolve(strict=True)
        if mode not in ('capture', 'restore'):
            raise ValueError('Unknown backup operation')
        {'capture': capture, 'restore': restore}[mode](root)
        print('Empty XBT wallet backup check OK')
    except Exception:
        raise SystemExit('Empty-wallet backup/restore refused; private details withheld. Keep the original wallet and backup.')
