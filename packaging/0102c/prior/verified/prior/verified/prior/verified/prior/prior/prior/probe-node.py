#!/usr/bin/env python3
"""Inspect the separate test node; optional canary requires an empty wallet."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path('/root/.lightning')
IDENTITY = dict(schema=1, profile='xbt-privkeyio-v1', layout='bitcoin')
KEY = ['xbt-cln-candidate', '0090-backup-canary']
CANARY = 'This entry must disappear when the channel database is excluded from backup.'


def need(ok, reason):
    if not ok: raise RuntimeError(reason)


def read_json(path):
    need(path.is_file() and not path.is_symlink() and path.stat().st_size < 1048576,
         'Expected ordinary configuration file: ' + path.name)
    return json.loads(path.read_text())


def rpc(method, **params):
    args = ['lightning-cli', '--lightning-dir=' + str(ROOT), '--json', '--notifications=none', '-k', method]
    args += [k + '=' + json.dumps(v, separators=(',', ':')) for k, v in params.items()]
    p = subprocess.run(args, text=True, capture_output=True, timeout=30)
    need(p.returncode == 0, 'Readiness check failed at ' + method + '; inspect local service logs')
    return json.loads(p.stdout)


def inspect(prepare=False):
    need(read_json(ROOT / 'xbt-package-identity.json') == IDENTITY, 'Wrong node package/profile')
    lock = read_json(Path('/usr/local/share/xbt-cln/source-lock.json'))
    need(lock['engine_patch']['version'] == 'v26.06.9-blake2b.7-swap0088b', 'Unexpected candidate engine')
    for base in (ROOT, ROOT / 'bitcoin'):
        for name in ['bounded-authority-v1', 'remote-authority-v1', 'customer-remote-v1',
                     'customer-invoices-v1', 'swap-gate-v1']:
            need(not (base / name).exists(), 'Swap state present; this test is for the separate node-only VM')
    info = rpc('getinfo')
    need(info['network'] == 'bitcoin' and re.fullmatch('0[23][0-9a-f]{64}', info['id']) is not None,
         'Unexpected node identity')
    for place in ('init', 'node', 'invoice'):
        value = info['our_features'][place]
        need(re.fullmatch('(?:[0-9a-fA-F]{2})+', value) is not None, 'Invalid chain features')
        bits = int(value, 16)
        need(bits & (1 << 512) and not bits & (1 << 513), 'Wrong XBT chain feature')
        need((not bits & (3 << 514)) if place == 'invoice' else
             (bits & (1 << 515) and not bits & (1 << 514)), 'Wrong unified signing feature')
    need(info['version'].lstrip('v') == '26.06.9-blake2b.7-swap0088b', 'Running engine version differs')
    funds = rpc('listfunds'); peers = rpc('listpeerchannels')['channels']
    closed = rpc('listclosedchannels')['closedchannels']
    invoices = rpc('listinvoices')['invoices']; pays = rpc('listsendpays')['payments']
    empty = (funds['outputs'] == [] and funds['channels'] == [] and peers == [] and closed == []
             and not any(i.get('status') == 'paid' for i in invoices) and pays == [])
    restored = (ROOT / 'node-restored.json').exists()
    store = read_json(ROOT / 'store.json')
    rows = rpc('listdatastore', key=KEY)['datastore']
    if prepare:
        need(empty and not restored, 'Backup canary requires a fresh, unfunded, never-channelled test wallet')
        need(not info.get('warning_bitcoind_sync') and not info.get('warning_lightningd_sync'), 'Node must be synced')
        if rows:
            need(len(rows) == 1 and rows[0].get('key') == KEY and rows[0].get('string') == CANARY,
                 'Existing canary differs; no changes made')
        else:
            rpc('datastore', key=KEY, string=CANARY, mode='must-create')
            rows = rpc('listdatastore', key=KEY)['datastore']
        need(len(rows) == 1 and rows[0].get('string') == CANARY, 'Canary not recorded')
    plugins = rpc('plugin', subcommand='list')['plugins']
    active = {Path(p['name']).name for p in plugins if p.get('active') is True}
    binary_sha = hashlib.sha256(Path('/usr/local/bin/lightningd').read_bytes()).hexdigest()
    return dict(schema=1, candidate='0090', read_only=not prepare, profile=IDENTITY['profile'],
        version=info['version'], node_fingerprint=hashlib.sha256(info['id'].encode()).hexdigest(),
        engine_sha256=binary_sha, blockheight=info['blockheight'],
        synced=not info.get('warning_bitcoind_sync') and not info.get('warning_lightningd_sync'),
        empty_test_wallet=empty, channel_count=len(peers), closed_channel_count=len(closed),
        wallet_output_count=len(funds['outputs']), restored_marker=restored,
        restore_pending=store.get('restore') is True, rescan_pending=store.get('rescan') is not None,
        ui_credential_file_present=(ROOT / '.commando-env').is_file(),
        emergency_recovery_file_present=(ROOT / 'bitcoin/emergency.recover').is_file(),
        preserved_recovery_copies=len(list((ROOT / 'bitcoin').glob('emergency.recover.restored-*'))),
        backup_canary_present=any(r.get('key') == KEY and r.get('string') == CANARY for r in rows),
        native_plugins_ready={'clnrest', 'cln-grpc', 'cln-askrene', 'cln-xpay', 'sql', 'bookkeeper', 'chanbackup'} <= active)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare-empty-backup', action='store_true',
                   help='Write one non-secret database canary, only on the empty test wallet')
    args = p.parse_args()
    try: print(json.dumps(inspect(args.prepare_empty_backup), indent=2))
    except Exception as e:
        print(json.dumps(dict(result='REFUSED', reason=str(e))))
        raise SystemExit(1)
