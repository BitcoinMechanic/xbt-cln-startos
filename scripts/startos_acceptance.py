#!/usr/bin/env python3
"""Record or verify small, redacted probes from the empty StartOS test node."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shlex
import subprocess

ENGINE = 'bb272c7a51c821558f0b623f563b2f0bc2d6d3bea2f175fc15e2f5206d6c1430'
VERSION = 'v26.06.9-blake2b.7-swap0088b'
FILES = {stage: 'xbt-0090-canary-' + stage + '.json'
         for stage in ('before-backup', 'after-backup', 'restored')}
FIELDS = set('schema candidate read_only profile version node_fingerprint engine_sha256 blockheight '
    'synced empty_test_wallet channel_count closed_channel_count wallet_output_count restored_marker '
    'restore_pending rescan_pending ui_credential_file_present emergency_recovery_file_present '
    'preserved_recovery_copies backup_canary_present native_plugins_ready'.split())


def need(ok, message):
    if not ok: raise RuntimeError(message)


def ordinary(path):
    path = path.expanduser().absolute()
    need(not any(p.is_symlink() for p in (path, *path.parents)), 'Symlinked receipt path refused')
    return path


def read(path):
    path = ordinary(path)
    need(path.is_file() and path.stat().st_size < 65536,
         'Missing or oversized acceptance receipt: ' + str(path))
    return json.loads(path.read_text())


def validate(report, stage, baseline=None):
    need(type(report) is dict and set(report) == FIELDS, 'Unexpected probe fields; use the supplied redacted probe')
    fixed = dict(schema=1, candidate='0090', profile='xbt-privkeyio-v1', version=VERSION,
                 engine_sha256=ENGINE, read_only=stage != 'before-backup',
                 empty_test_wallet=True, channel_count=0, closed_channel_count=0,
                 wallet_output_count=0, restored_marker=stage == 'restored',
                 backup_canary_present=stage != 'restored',
                 ui_credential_file_present=True, emergency_recovery_file_present=True,
                 native_plugins_ready=True)
    for key, expected in fixed.items():
        need(type(report[key]) is type(expected) and report[key] == expected,
             stage + ': ' + key + ' differs')
    need(type(report['node_fingerprint']) is str and re.fullmatch('[0-9a-f]{64}', report['node_fingerprint']),
         'Invalid redacted node fingerprint')
    need(type(report['blockheight']) is int and report['blockheight'] >= 961640, 'Unexpected XBT height')
    copies = report['preserved_recovery_copies']
    need(type(copies) is int and (copies >= 1 if stage == 'restored' else copies == 0),
         'Recovery copy count differs')
    if baseline:
        for key in ('node_fingerprint', 'engine_sha256'):
            need(report[key] == baseline[key], 'Different wallet or engine: ' + key)
    need(report['restore_pending'] is False,
         'Recovery setup is still pending. Leave the service running for emergency recovery and address preparation; retry this read-only check after the Web UI is ready.')
    need(report['rescan_pending'] is False, 'A rescan request is still pending; retry after startup consumes it')
    need(report['synced'] is True, 'The node is still syncing; this receipt is not complete')
    return report


def verify_directory(directory):
    directory = ordinary(directory)
    reports = {}
    for stage, name in FILES.items():
        reports[stage] = validate(read(directory/name), stage, reports.get('before-backup'))
    return dict(schema=1, kind='verified-empty-wallet-startos-probes',
        engine_sha256=ENGINE, node_fingerprint=reports['before-backup']['node_fingerprint'],
        snapshots=reports, files_sha256={name: hashlib.sha256((directory/name).read_bytes()).hexdigest()
                                       for name in FILES.values()},
        full_history_rescan_verified=False, funded_startos_recovery_verified=False,
        legacy_migration_verified=False, swaps_active=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt-dir', type=Path, required=True)
    parser.add_argument('--probe', choices=tuple(FILES))
    parser.add_argument('--destination', help='Explicit test StartOS SSH destination; no default host')
    args = parser.parse_args()
    directory = ordinary(args.receipt_dir)
    if not args.probe:
        verify_directory(directory)
        print('PASS: all three empty-wallet backup/restore receipts match.')
        return
    need(args.destination and not args.destination.startswith('-') and
         re.fullmatch(r'[A-Za-z0-9_.@:\[\]-]+', args.destination), 'Explicit SSH destination required')
    baseline = read(directory/FILES['before-backup']) if args.probe != 'before-backup' else None
    if baseline: validate(baseline, 'before-backup')
    source = (Path(__file__).resolve().parent/'probe-node.py').read_text()
    command = ['start-cli', 'package', 'attach', '--name', 'lightning-sub',
               'xbt-cln', '--', '/usr/bin/python3', '-u', '-c', source]
    if args.probe == 'before-backup': command.append('--prepare-empty-backup')
    result = subprocess.run(['ssh', '-nT', '-o', 'ConnectTimeout=10', args.destination, shlex.join(command)],
                            capture_output=True, text=True, timeout=90)
    need(result.returncode == 0, 'Probe unavailable. Check that the test XBT service is running; no completed receipt saved.')
    report = json.loads(result.stdout)
    # Never print an unexpected/unredacted response.
    need(type(report) is dict and set(report) == FIELDS, 'Unexpected probe response')
    print(json.dumps(report, indent=2))
    validate(report, args.probe, baseline)
    directory.mkdir(parents=True, exist_ok=True)
    target = ordinary(directory/FILES[args.probe])
    if target.exists():
        old = validate(read(target), args.probe, baseline)
        need(old['node_fingerprint'] == report['node_fingerprint'], 'Existing receipt belongs to another wallet; retained')
        print('PASS: current check passed; existing completed receipt retained: ' + str(target))
    else:
        with target.open('x') as f: f.write(json.dumps(report, indent=2)+'\n')
        print('PASS: receipt saved: ' + str(target))


if __name__ == '__main__':
    try: main()
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as error:
        raise SystemExit('Acceptance check: ' + str(error)) from None
