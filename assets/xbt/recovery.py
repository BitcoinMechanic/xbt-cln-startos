#!/usr/bin/env python3
"""Bounded stopped-wallet backup and force-close recovery orchestration.

Never restores SQLite or resumes channels from a stale database. The receipt is
an integrity binding, not authentication against a modified backup. Completion
requires manual review; ONCHAIN alone is not evidence that funds were recovered.
"""
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time

from empty_backup import atomic_json, digest, regular

RECEIPT = 'recovery-backup.json'
INTENT = 'recovery-intent.json'
STATUS = 'recovery-status.json'
BIRTH = 'wallet-birth.json'
NODE = r'0[23][0-9a-f]{64}'
CID = r'[0-9a-f]{64}'


def check(ok, message):
    if not ok:
        raise ValueError(message)


def layout(network):
    check(network in ('xbt', 'xbt-regtest'), 'Unexpected recovery network')
    chain = hashlib.sha256(f'BitcoinMechanic/lightning:experimental:{network}:v1'.encode()).digest()
    # Both identities are stored in internal reverse-of-display byte order.
    chain = chain[::-1]
    return f'{network}/lightningd.sqlite3', f'{network}/hsm_secret', f'{network}/emergency.recover', chain


def load(root, name):
    p = regular(root, name)
    check(p.stat().st_size <= 65536, 'Oversized recovery record')
    return json.loads(p.read_text())


def validate(r, network):
    check(r.get('schema') == 1 and r.get('network') == network
          and re.fullmatch(NODE, r.get('node_id', '')), 'Invalid recovery identity')
    ids = r.get('channels')
    check(isinstance(ids, list) and len(ids) <= 8 and len(ids) == len(set(ids))
          and all(isinstance(c, str) and re.fullmatch(CID, c) for c in ids),
          'Invalid recovery channel set')
    valid_height(r.get('scan_start', 1))
    return r


def valid_height(height):
    check(type(height) is int and 1 <= height <= 2147483647, 'Invalid scan starting height')
    return height


def record_birth(root, height, network='xbt'):
    """Called after backend verification, BEFORE first key/database creation."""
    valid_height(height)
    db, key, _, _ = layout(network)
    if os.path.lexists(root / BIRTH):
        birth = load(root, BIRTH)
        check(birth.get('schema') == 1 and birth.get('network') == network,
              'Invalid wallet birth record')
        valid_height(birth['scan_start'])
        return
    if any(os.path.lexists(root / name) for name in (key, db, INTENT, 'restored-identity.json')):
        return  # An existing/imported wallet has no provable birthday here.
    atomic_json(root, BIRTH, {'schema': 1, 'network': network,
                             'scan_start': max(1, height - 144)})


def check_empty_database(root, r, network):
    db, key, _, chain = layout(network)
    check(digest(root, key) == r['key_sha256'], 'Recovery key changed')
    if os.path.lexists(root / db):
        path = regular(root, db)
        wal = root / (db + '-wal')
        check(not wal.exists() or regular(root, db + '-wal').stat().st_size == 0,
              'Stop the service cleanly before changing scan start')
        con = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
        try:
            con.execute('PRAGMA query_only=ON')
            check(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Database check failed')
            check(con.execute("SELECT blobval FROM vars WHERE name='genesis_hash'").fetchall() == [(chain,)], 'Wrong chain')
            check(con.execute("SELECT blobval FROM vars WHERE name='node_id'").fetchall()
                  == [(bytes.fromhex(r['node_id']),)], 'Wrong database identity')
            for table in ('channels', 'channel_htlcs', 'outputs', 'transactions', 'payments', 'invoices'):
                check(not con.execute('SELECT 1 FROM ' + table + ' LIMIT 1').fetchone(),
                      'Recorded wallet activity prevents this action')
        finally:
            con.close()


def set_empty_scan_start(root, height, acknowledged, network='xbt'):
    """Stopped-service escape hatch for an explicitly attested never-funded key."""
    valid_height(height)
    check(acknowledged is True, 'Never-funded confirmation required')
    r = validate(load(root, INTENT), network)
    check(r['phase'] == 'prepared' and r['channels'] == [],
          'Only a not-yet-imported, channel-free recovery can use this action')
    check_empty_database(root, r, network)
    atomic_json(root, INTENT, {**r, 'scan_start': height,
                               'scan_source': 'operator-confirmed-never-funded'})
    atomic_json(root, STATUS, {'phase': 'prepared', 'complete': False, 'scan_start': height})


def finish_empty(root, acknowledged, network='xbt'):
    check(acknowledged is True, 'Never-funded confirmation required')
    with (root / 'recovery.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        r = validate(load(root, INTENT), network)
        check(r.get('phase') in ('imported', 'finished-empty') and r['channels'] == [],
              'Only an imported channel-free recovery can be finished here')
        check(not os.path.lexists(root / 'restore-blocked'), 'Restore remains blocked')
        regular(root, layout(network)[0])  # Unlike scan adjustment, DB must exist.
        check_empty_database(root, r, network)
        if r['phase'] == 'finished-empty':
            check(r.get('completion_scope') == 'operator-confirmed-never-funded',
                  'Invalid completed recovery record')
            return  # Idempotent; do not change audit timestamps.
        status = load(root, STATUS)
        check(status.get('phase') == 'monitoring'
              and all(status.get(k) == 0 for k in ('expected_channels', 'waiting_for_close', 'onchain_channels')),
              'Recovery has not reached empty-wallet monitoring')
        checked = status.get('checked_at')
        check(type(checked) in (int, float) and 0 <= time.time() - checked <= 600,
              'Recovery status is stale; start then stop the service to refresh it')
        # A single atomic transition retains history and is the startup decision.
        # No marker, key, backup, or wallet database is deleted.
        atomic_json(root, INTENT, {**r, 'phase': 'finished-empty',
                                   'completion_scope': 'operator-confirmed-never-funded',
                                   'completed_at': int(time.time())})


def capture(root, network='xbt'):
    (root / RECEIPT).unlink(missing_ok=True)
    # Do not back up a partly recovered wallet as if it were an intact original.
    check(not any(os.path.lexists(root / n) for n in
                  ('restore-blocked', 'bitcoin')), 'Recovery or foreign wallet present')
    completed = None
    if os.path.lexists(root / INTENT):
        completed = validate(load(root, INTENT), network)
        check(completed.get('phase') == 'finished-empty' and completed['channels'] == []
              and completed.get('completion_scope') == 'operator-confirmed-never-funded',
              'Recovery has not been completed')
    db, key, scb, chain = layout(network)
    database = regular(root, db)
    wal = root / (db + '-wal')
    check(not wal.exists() or (regular(root, db + '-wal').stat().st_size == 0),
          'Database is not checkpointed')
    con = sqlite3.connect(database.as_uri() + '?mode=ro', uri=True)
    try:
        con.execute('PRAGMA query_only=ON')
        check(con.execute('PRAGMA quick_check').fetchall() == [('ok',)], 'Database check failed')
        check(con.execute("SELECT blobval FROM vars WHERE name='genesis_hash'").fetchall()
              == [(chain,)], 'Wrong chain')
        node = con.execute("SELECT blobval FROM vars WHERE name='node_id'").fetchone()[0].hex()
        for name in ('bip32_max_index', 'bip86_max_index'):
            rows = con.execute('SELECT intval FROM vars WHERE name=?', (name,)).fetchall()
            check(not rows or (len(rows) == 1 and type(rows[0][0]) is int
                              and 0 <= rows[0][0] <= 50), 'Address scan bound exceeded')
        check(not con.execute('SELECT 1 FROM channel_htlcs WHERE hstate IS NULL OR hstate NOT IN (9,19) LIMIT 1').fetchone(),
              'Unresolved HTLCs are not supported')
        check(not con.execute('SELECT 1 FROM channel_funding_inflights LIMIT 1').fetchone(),
              'Inflight channel funding is not supported')
        channels = con.execute('SELECT full_channel_id, state FROM channels').fetchall()
        check(all(state == 3 for _, state in channels), 'Only settled normal channels supported')
        ids = [cid.hex() for cid, _ in channels]
        # No unconfirmed or reserved inputs in this first backup profile.
        check(not con.execute('SELECT 1 FROM outputs WHERE status = 1 OR (status = 0 AND confirmation_height IS NULL) LIMIT 1').fetchone(),
              'Reserved or unconfirmed wallet outputs are not supported')
    finally:
        con.close()
    scan_start = completed.get('scan_start', 1) if completed else 1
    if completed:
        check(completed['node_id'] == node and completed['key_sha256'] == digest(root, key),
              'Completed recovery identity changed')
    if os.path.lexists(root / BIRTH):
        birth = load(root, BIRTH)
        check(birth.get('schema') == 1 and birth.get('network') == network, 'Invalid wallet birth record')
        scan_start = min(scan_start, valid_height(birth['scan_start'])) if completed else valid_height(birth['scan_start'])
    receipt = validate({'scan_start': scan_start, 'schema': 1, 'network': network, 'node_id': node,
                        'channels': ids, 'key_sha256': digest(root, key),
                        'scb_sha256': digest(root, scb)}, network)
    atomic_json(root, RECEIPT, receipt)


def restore(root, network='xbt'):
    atomic_json(root, 'restore-blocked', {'blocked': True})
    db, key, scb, _ = layout(network)
    check(not any(os.path.lexists(root / n) for n in (db, db+'-wal', db+'-shm', 'bitcoin')),
          'Restore requires a fresh volume')
    r = validate(load(root, RECEIPT), network)
    check(digest(root, key) == r['key_sha256'] and digest(root, scb) == r['scb_sha256'],
          'Recovery files changed')
    atomic_json(root, 'restored-identity.json', {'schema': 1, 'node_id': r['node_id']})
    atomic_json(root, INTENT, {**r, 'phase': 'prepared'})
    atomic_json(root, STATUS, {'phase': 'prepared', 'complete': False})
    (root / 'restore-blocked').unlink()


def call(root, network, method):
    p = subprocess.run(['lightning-cli', f'--lightning-dir={root}',
                        f'--network={network}', '--json', '--notifications=none', method],
                       text=True, capture_output=True, timeout=60)
    check(p.returncode == 0, 'Recovery RPC unavailable')
    return json.loads(p.stdout)


def step(root, network='xbt', rpc=None):
    r = validate(load(root, INTENT), network)
    rpc = rpc or (lambda method: call(root, network, method))
    check(r.get('phase') in ('prepared', 'importing', 'imported'), 'Invalid recovery phase')
    _, key, _, _ = layout(network)
    check(digest(root, key) == r['key_sha256'], 'Recovery key changed')
    info = rpc('getinfo')
    check(info['network'] == network and info['id'] == r['node_id'], 'RPC identity changed')
    if any(k.startswith('warning_') for k in info):
        return {'phase': 'scanning', 'complete': False, 'scan_start': r.get('scan_start', 1)}
    expected = set(r['channels'])
    if r['phase'] != 'imported':
        current = rpc('listpeerchannels')['channels']
        known = {c['channel_id'] for c in current}
        check(known <= expected, 'Unexpected channel in recovery wallet')
        missing = expected - known
        if missing:
            scb = rpc('getemergencyrecoverdata')
            backed = set(scb['backed_up_channel_ids'])
            check(expected <= backed, 'Backup does not contain expected channels')
            if r['phase'] == 'prepared':
                check(hashlib.sha256(bytes.fromhex(scb['filedata'])).hexdigest() == r['scb_sha256'],
                      'Loaded channel backup changed')
            atomic_json(root, INTENT, {**r, 'phase': 'importing'})
            # Idempotent: CLN skips channels already present. A lost reply leaves
            # importing on disk and the next step reconciles the channel set.
            rpc('emergencyrecover')
            known = {c['channel_id'] for c in rpc('listpeerchannels')['channels']}
            check(expected <= known, 'Channel recovery import incomplete')
        atomic_json(root, INTENT, {**r, 'phase': 'imported'})
    channels = rpc('listpeerchannels')['channels']
    check(all(c['channel_id'] in expected for c in channels), 'Unexpected recovery channel')
    return {'phase': 'monitoring', 'complete': False, 'scan_start': r.get('scan_start', 1),
            'expected_channels': len(expected),
            'waiting_for_close': sum(c['state'] not in ('ONCHAIN', 'CLOSED') for c in channels),
            'onchain_channels': sum(c['state'] == 'ONCHAIN' for c in channels),
            'manual_review_required': True}


def run(root, network='xbt'):
    # A stable lock file survives replacement of intent/status records.
    with (root / 'recovery.lock').open('a') as f:
        fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        while True:
            try:
                status = step(root, network)
            except Exception:
                status = {'phase': 'attention', 'complete': False,
                          'message': 'Recovery check failed; retain original backup and inspect locally'}
            atomic_json(root, STATUS, {**status, 'checked_at': int(time.time())})
            time.sleep(5)


if __name__ == '__main__':
    try:
        mode, directory, *extra = sys.argv[1:]
        root = Path(directory).resolve(strict=True)
        if mode == 'record-birth':
            check(len(extra) == 1, 'Expected backend height')
            record_birth(root, int(extra[0]))
        elif mode == 'finish-empty':
            check(extra == ['--confirm-never-funded'], 'Confirmation required')
            finish_empty(root, True)
        elif mode == 'set-empty-scan-start':
            check(len(extra) == 2 and extra[1] == '--confirm-never-funded', 'Confirmation required')
            set_empty_scan_start(root, int(extra[0]), True)
        else:
            network = extra[0] if extra else 'xbt'
            check(len(extra) <= 1 and mode in ('capture', 'restore', 'run'), 'Invalid operation')
            if mode == 'restore' and not (root / RECEIPT).exists():
                check(network == 'xbt', 'Legacy receipt only supports XBT')
                from empty_backup import restore as empty_restore
                empty_restore(root)
            else:
                {'capture': capture, 'restore': restore, 'run': run}[mode](root, network)
    except Exception:
        raise SystemExit('Recovery operation refused; retain wallet and backup. Private details withheld.')
