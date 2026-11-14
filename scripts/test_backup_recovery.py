#!/usr/bin/env python3
"""Stopped-volume backup hooks + funded recovery with the retained UI and patched fee estimator.

The StartOS supervisor and rsync transport are not running here. A strict file
copy uses the package's actual exclusions. Only while stopped, the fixture maps
regtest/ to bitcoin/ for the actual package filesystem hooks, then maps it back.
The production identity checks have no bypass. Recovery uses the exact package
commands with a regtest CLI adapter, never an existing wallet.
"""
import argparse
from decimal import Decimal
import fnmatch
import hashlib
import json
import os
import re
from pathlib import Path
import shutil
import signal
import sqlite3
import subprocess
import sys
import time

sys.path.insert(0, '/opt/fixture')
from test_node_ui import NodeLab, Ui as BaseUi, ci, require


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sats(value):
    n = Decimal(str(value)) * 100000000
    require(n == n.to_integral_value(), 'nonintegral_chain_amount')
    return int(n)


def hook(mode, volume, runtime):
    p = subprocess.run(['/usr/local/bin/node', '/opt/recovery/hooks/index.js',
                        mode, str(volume), str(runtime)], text=True, capture_output=True)
    require(p.returncode == 0, 'package_'+mode+'_hook_failed: '+p.stderr[-3000:])
    return json.loads(p.stdout)


def snapshot(source, destination, excludes):
    require(not destination.exists(), 'snapshot_destination_exists')
    destination.mkdir()
    for p in sorted(source.rglob('*')):
        rel = p.relative_to(source).as_posix()
        if any(fnmatch.fnmatchcase(rel, pattern) for pattern in excludes):
            continue
        require(not p.is_symlink(), 'fixture_snapshot_symlink')
        q = destination / rel
        if p.is_dir(): q.mkdir(exist_ok=True)
        else:
            require(p.is_file(), 'unexpected_special_file_in_snapshot: '+rel)
            q.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, q)


def normal(lab, node, count):
    rows = lab.rpc(node['cli'], 'listpeerchannels')['channels']
    if len(rows) == count and all(r['state'] == 'CHANNELD_NORMAL' and
            r['peer_connected'] and r.get('reestablished') and r.get('htlcs') == [] for r in rows):
        return [ci.channel(r, ci.PRIVKEYIO_XBT) for r in rows]


def available(lab, node):
    return {(o['txid'], o['output']): o for o in lab.rpc(node['cli'], 'listfunds')['outputs']
            if o['status'] == 'confirmed' and not o.get('reserved', False)}


class Ui(BaseUi):
    def rpc(self, method, **params):
        status, reply = self.request('POST', '/v1/cln/call', dict(method=method, params=params))
        if status != 200:
            # Disposable diagnostics: retain the error, never raw transaction data.
            detail = re.sub(r'(?i)\b(?:ln(?:bc|bcrt|xbt)[0-9a-z]+|[0-9a-z_+/=-]{64,})\b',
                            '[redacted]', json.dumps(reply))[:4096]
            with (self.root/'rpc-errors.jsonl').open('a') as out:
                out.write(json.dumps(dict(method=method, status=status, error=detail))+'\n')
            raise RuntimeError('ui_rpc_failed_'+method+'_'+str(status)+': '+detail)
        return reply


class RecoveryLab(NodeLab):
    engine_versions = dict(NodeLab.engine_versions, **{
        ci.PRIVKEYIO_XBT: ('v26.06.9-blake2b.7-swap0088b', '26.06.9-blake2b.7-swap0088b')})

    def __init__(self, args):
        super().__init__(args)
        self.rescan_names = set()

    def start(self, command, log):
        if str(command[0]) == '/usr/local/bin/lightningd' and log.parent.name in self.rescan_names:
            command = [*command, '--rescan=-1']
        return super().start(command, log)


def command(lab, node, argv, logname):
    # Both substitutions are confined to this fixture; production remains mainnet.
    cli = '/usr/local/bin/lightning-cli --network=regtest'
    if argv[0] == 'lightning-cli':
        return lab.rpc(['/usr/local/bin/lightning-cli', '--network=regtest', argv[1],
                        '--json', '--notifications=none'], *argv[2:])
    require(argv[:2] == ['sh', '-c'] and argv[2].count('lightning-cli ') == 1,
            'unexpected_package_recovery_command')
    adapted = ['sh', '-c', argv[2].replace('lightning-cli ', cli+' ')]
    proc = lab.start(adapted, node['root']/logname)
    deadline = time.monotonic()+1800
    next_report = time.monotonic()+30
    while proc.poll() is None:
        require(node['proc'].poll() is None, 'node_exited_during_address_recovery')
        require(time.monotonic() < deadline, 'address_recovery_timeout')
        if time.monotonic() >= next_report:
            print('0088: package address pre-generation is still running', flush=True)
            next_report = time.monotonic()+30
        time.sleep(.2)
    require(proc.returncode == 0, 'package_address_recovery_failed')


def run(lab):
    lab.checkpoint('backup-recovery-fund-two-channel-roles')
    backend = lab.backend('xbt-chain', True)
    node = lab.lightning('recovering', ci.PRIVKEYIO_XBT, backend)
    peers = [lab.lightning(name, ci.PRIVKEYIO_XBT, backend) for name in ('receiver-peer', 'opener-peer')]
    ui = Ui(lab, node)
    identity = node['identity']
    deposits = []
    def deposit(address, amount):
        txid = lab.rpc(backend['cli'], 'sendtoaddress', address, str(Decimal(amount)/100000000))
        tx = lab.rpc(backend['cli'], 'getrawtransaction', txid, 'true')
        outs = [o for o in tx['vout'] if o['scriptPubKey'].get('address') == address]
        require(len(outs) == 1 and sats(outs[0]['value']) == amount, 'deposit_mismatch')
        deposits.append(dict(txid=txid, vout=outs[0]['n'], sats=amount))
        return (txid, outs[0]['n'])
    deposit(ui.rpc('newaddr', addresstype='bech32')['bech32'], 1000000)
    deposit(lab.rpc(peers[1]['cli'], 'newaddr', 'bech32')['bech32'], 400000)
    lab.mine(backend); lab.synced(backend, node, *peers)
    for peer in peers:
        lab.rpc(node['cli'], 'connect', peer['identity']['node_id'], '127.0.0.1', peer['port'])
    first = ui.rpc('fundchannel', id=peers[0]['identity']['node_id'], amount=300000, push_msat=50000000)
    second = lab.rpc_named(peers[1]['cli'], 'fundchannel',
                          dict(id=identity['node_id'], amount=300000, push_msat=50000000))
    lab.mine(backend); lab.synced(backend, node, *peers)
    rows = lab.wait(lambda: normal(lab, node, 2), node['proc'])
    for peer in peers: lab.wait(lambda: normal(lab, peer, 1), peer['proc'])
    funding = {r['funding_txid'] for r in rows}
    require(funding == {first['txid'], second['txid']}, 'funding_receipt_mismatch')
    channel_ids = {r['channel_id'] for r in rows}
    balances = {r['funding_txid']: r['to_us_msat']//1000 for r in rows}
    # Both address types, well beyond the 50-key lookahead, across an unused gap.
    for _ in range(128): high = lab.rpc(node['cli'], 'newaddr', 'all')
    high_outputs = {deposit(high['bech32'], 12345), deposit(high['p2tr'], 23456)}
    lab.mine(backend, 40); lab.synced(backend, node, *peers)
    before_outputs = available(lab, node)
    require(high_outputs <= before_outputs.keys(), 'high_index_deposits_not_seen')
    require(set(lab.rpc(node['cli'], 'getemergencyrecoverdata')['backed_up_channel_ids']) == channel_ids,
            'SCB_not_current')
    lab.checkpoint('stopped-volume-backup-without-channel-database')
    for p in (ui.proc, node['proc'], *(n['proc'] for n in peers)): lab.stop(p)
    # Snapshot a stopped wallet; only disposable channel states are advanced below.
    volume = node['root']
    (volume/'regtest').rename(volume/'bitcoin')
    (volume/'xbt-package-identity.json').write_text(json.dumps(dict(schema=1, profile='xbt-privkeyio-v1', layout='bitcoin')))
    (volume/'.commando-env').write_text('fixture-generated-credential-must-be-excluded')
    spec = hook('before', volume, lab.root/'restored')
    backup = lab.root/'backup'
    snapshot(volume, backup, spec['excludes'])
    forbidden = ('lightningd.sqlite3', 'lightningd.sqlite3-wal', 'lightningd.sqlite3-shm', 'lightning-rpc', 'gossip_store')
    require(all(not (backup/'bitcoin'/n).exists() for n in forbidden) and not (backup/'.commando-env').exists(),
            'resumable_database_or_credential_in_backup')
    secret = digest(volume/'bitcoin/hsm_secret')
    scb = digest(volume/'bitcoin/emergency.recover')
    password = digest(volume/'ui/config.json')
    require(digest(backup/'bitcoin/hsm_secret') == secret and digest(backup/'bitcoin/emergency.recover') == scb,
            'backup_key_or_SCB_changed')
    # Make the backup stale: advance both channel states after the snapshot.
    # Emergency data must recover today's balances, not resurrect old commitments.
    lab.checkpoint('advance-both-channels-after-backup')
    (volume/'bitcoin').rename(volume/'regtest')
    node = lab.lightning('recovering', ci.PRIVKEYIO_XBT, backend)
    peers = [lab.lightning(n['root'].name, ci.PRIVKEYIO_XBT, backend) for n in peers]
    for peer in peers:
        lab.rpc(node['cli'], 'connect', peer['identity']['node_id'], '127.0.0.1', peer['port'])
    lab.wait(lambda: normal(lab, node, 2), node['proc'])
    for sender, receiver, amount, label in ((node, peers[0], 5000000, 'post-backup-out'),
                                           (peers[1], node, 7000000, 'post-backup-in')):
        invoice = lab.rpc(receiver['cli'], 'invoice', amount, label, 'Disposable stale-backup proof')
        ci.invoice(lab.rpc(sender['cli'], 'decode', invoice['bolt11']), ci.PRIVKEYIO_XBT, 'regtest')
        require(lab.rpc(sender['cli'], 'pay', invoice['bolt11'], timeout=90)['status'] == 'complete',
                'post_backup_payment_failed')
        row = lab.rpc(receiver['cli'], 'listinvoices', label)['invoices']
        require(len(row) == 1 and row[0]['status'] == 'paid' and row[0]['amount_received_msat'] == amount,
                'post_backup_invoice_not_paid')
        lab.wait(lambda: normal(lab, node, 2), node['proc'])
        for peer in peers: lab.wait(lambda: normal(lab, peer, 1), peer['proc'])
    advanced = normal(lab, node, 2)
    new_balances = {r['funding_txid']: r['to_us_msat']//1000 for r in advanced}
    require(new_balances[first['txid']] == balances[first['txid']]-5000 and
            new_balances[second['txid']] == balances[second['txid']]+7000, 'post_backup_balances_wrong')
    balances = new_balances
    for n in (node, *peers): lab.stop(n['proc'])
    # The advanced source wallet is now the simulated lost state. Never reopen it.
    restored_root = lab.root/'restored'
    shutil.copytree(backup, restored_root)
    commands = hook('after', restored_root, restored_root)['commands']
    copies = list((restored_root/'bitcoin').glob('emergency.recover.restored-*'))
    require(len(copies) == 1 and digest(copies[0]) == scb, 'original_recovery_copy_missing')
    marker = json.loads((restored_root/'node-restored.json').read_text())
    require(marker == dict(schema=1, recovery=True), 'persistent_restore_marker_missing')
    (restored_root/'bitcoin').rename(restored_root/'regtest')
    require(not (restored_root/'regtest/lightningd.sqlite3').exists(), 'restore_copied_live_database')
    lab.checkpoint('emergency-stubs-and-interrupted-recovery')
    lab.rescan_names.add('restored')
    restored = lab.lightning('restored', ci.PRIVKEYIO_XBT, backend)
    lab.rescan_names.remove('restored')
    lab.synced(backend, restored)
    require(restored['identity'] == identity, 'recovered_identity_changed')
    stubs = command(lab, restored, commands['emergency'], 'emergency.log')['stubs']
    require(set(stubs) == channel_ids and len(stubs) == 2, 'original_channels_not_recovered')
    lab.wait(lambda: before_outputs.keys()-high_outputs <= available(lab, restored).keys(), restored['proc'])
    require(not high_outputs.intersection(available(lab, restored)), 'high_index_negative_control_not_reproduced')
    # Crash with recovery stubs durable, before any peer can close the channels.
    os.killpg(restored['proc'].pid, signal.SIGKILL); restored['proc'].wait(timeout=30)
    restored = lab.lightning('restored', ci.PRIVKEYIO_XBT, backend)
    require(restored['identity'] == identity, 'recovery_restart_identity_changed')
    command(lab, restored, commands['emergency'], 'emergency-repeat.log')
    recovered = lab.rpc(restored['cli'], 'listpeerchannels')['channels']
    require(len(recovered) == 2 and {r['channel_id'] for r in recovered} == channel_ids,
            'repeated_recovery_duplicated_or_lost_channels')
    for r in recovered: ci.channel(r, ci.PRIVKEYIO_XBT)
    lab.checkpoint('package-address-window-and-full-rescan')
    command(lab, restored, commands['addresses'], 'address-pregen.log')
    lab.stop(restored['proc'])
    with sqlite3.connect('file:'+str(restored_root/'regtest/lightningd.sqlite3')+'?mode=ro', uri=True) as db:
        indexes = dict(db.execute("SELECT name, intval FROM vars WHERE name IN ('bip32_max_index','bip86_max_index')"))
    require(max(indexes.get('bip32_max_index', 0), indexes.get('bip86_max_index', 0)) >= 10000,
            'package_address_window_not_persisted')
    # Equivalent to the requested Rescan Blockchain action from height 1.
    lab.rescan_names.add('restored')
    restored = lab.lightning('restored', ci.PRIVKEYIO_XBT, backend)
    lab.rescan_names.remove('restored')
    lab.synced(backend, restored)
    lab.wait(lambda: before_outputs.keys() <= available(lab, restored).keys(), restored['proc'])
    for outpoint, old in before_outputs.items():
        require(available(lab, restored)[outpoint]['amount_msat'] == old['amount_msat'], 'wallet_rescan_amount_changed')
    require(digest(restored_root/'ui/config.json') == password, 'UI_password_not_restored')
    ui = Ui(lab, restored)  # Existing password login against a fresh daemon/REST rune.
    require(ui.rpc('getinfo')['id'] == identity['node_id'], 'restored_UI_wrong_identity')
    lab.checkpoint('peer-force-closes-both-original-channels')
    peers = [lab.lightning(n['root'].name, ci.PRIVKEYIO_XBT, backend) for n in peers]
    for peer in peers:
        lab.rpc(restored['cli'], 'connect', peer['identity']['node_id'], '127.0.0.1', peer['port'])
    def closes():
        found = {}
        for txid in lab.rpc(backend['cli'], 'getrawmempool'):
            tx = lab.rpc(backend['cli'], 'getrawtransaction', txid, 'true')
            for vin in tx['vin']:
                if vin.get('txid') in funding: found[vin['txid']] = txid
        return found if set(found) == funding else None
    closing = lab.wait(closes, restored['proc'])
    all_nodes = [restored, *peers]
    for _ in range(18):
        lab.mine(backend, 20); lab.synced(backend, *all_nodes)
        time.sleep(.3)
        if all(not lab.rpc(n['cli'], 'listpeerchannels')['channels'] for n in all_nodes): break
    require(all(not lab.rpc(n['cli'], 'listpeerchannels')['channels'] for n in all_nodes),
            'channels_not_terminal_after_recovery')
    returned = available(lab, restored)
    require(before_outputs.keys() <= returned.keys(), 'original_wallet_outputs_lost')
    require(len(returned) >= len(before_outputs)+2, 'both_channel_recoveries_not_spendable')
    # Restart after resolution, before withdrawing: no second recovery or reopen.
    lab.stop(ui.proc); lab.stop(restored['proc'])
    restored = lab.lightning('restored', ci.PRIVKEYIO_XBT, backend); all_nodes[0] = restored
    require(available(lab, restored) == returned, 'resolved_wallet_changed_across_restart')
    require(json.loads((restored_root/'node-restored.json').read_text()) == marker, 'restore_warning_lost')
    ui = Ui(lab, restored)
    lab.checkpoint('withdraw-recovered-funds-and-reconcile-every-satoshi')
    sinks = []; withdrawals = []; withdrawal_fees = []
    for n in all_nodes:
        destination = lab.rpc(backend['cli'], 'getnewaddress')
        script = lab.rpc(backend['cli'], 'getaddressinfo', destination)['scriptPubKey']
        sinks.append(script)
        inputs = available(lab, n)
        result = ui.rpc('withdraw', destination=destination, satoshi='all') if n is restored else lab.rpc(n['cli'], 'withdraw', destination, 'all')
        tx = lab.rpc(backend['cli'], 'decoderawtransaction', result['tx'])
        used = {(i['txid'], i['vout']) for i in tx['vin']}
        require(used == set(inputs), 'withdraw_all_did_not_use_exact_available_outputs')
        fee = sum(o['amount_msat']//1000 for o in inputs.values()) - sum(sats(o['value']) for o in tx['vout'])
        mempool = lab.rpc(backend['cli'], 'getmempoolentry', result['txid'])
        require(fee > 0 and sats(mempool['fees']['base']) == fee, 'withdrawal_fee_mismatch')
        withdrawal_fees.append(dict(node=n['root'].name, fee_sats=fee, weight=tx['weight'],
                                    vsize=mempool['vsize'], default_feerate=True))
        (lab.root/'withdrawal-fees.json').write_text(json.dumps(withdrawal_fees, indent=2)+'\n')
        sigs = [bytes.fromhex(w) for i in tx['vin'] for w in i.get('txinwitness', [])
                if len(bytes.fromhex(w)) == 65 or (69 <= len(bytes.fromhex(w)) <= 73 and w.startswith('30'))]
        require(sigs and all(s[-1] & 0x20 for s in sigs), 'withdrawal_missing_unified_signature')
        withdrawals.append(result['txid'])
    lab.mine(backend, 6); lab.synced(backend, *all_nodes)
    require(all(not available(lab, n) for n in all_nodes), 'wallet_not_drained')
    # Walk confirmed descendants of the exact deposits. No txindex dependency.
    unspent = {(d['txid'], d['vout']): d['sats'] for d in deposits}
    fees = 0; received = 0; seen = set(); residue = {}; confirmed = []
    for height in range(102, lab.rpc(backend['cli'], 'getblockcount')+1):
        h = lab.rpc(backend['cli'], 'getblockhash', height)
        for tx in lab.rpc(backend['cli'], 'getblock', h, 2)['tx']:
            confirmed.append(tx)
            ins = [(i.get('txid'), i.get('vout')) for i in tx['vin']]
            if not any(i in unspent for i in ins): continue
            require(all(i in unspent for i in ins), 'unexpected_external_input_in_recovery_ledger')
            value = sum(unspent.pop(i) for i in ins)
            output_value = sum(sats(o['value']) for o in tx['vout'])
            require(value >= output_value, 'negative_transaction_fee')
            fees += value-output_value; seen.add(tx['txid'])
            for o in tx['vout']:
                amount = sats(o['value']); key = (tx['txid'], o['n'])
                if o['scriptPubKey']['hex'] in sinks: received += amount
                elif amount:
                    unspent[key] = amount; residue[key] = o['scriptPubKey']['hex']
    require(set(withdrawals) <= seen and set(closing.values()) <= seen, 'recovery_transactions_not_confirmed')
    # Attribute the restored node's channel proceeds, not merely the three-node total.
    by_id = {t['txid']: t for t in confirmed}
    owned = set(before_outputs)
    for f, closeid in closing.items():
        tx = by_id[closeid]
        expected = balances[f]
        if f == first['txid']:
            expected -= 300000-sum(sats(o['value']) for o in tx['vout'])
            expected -= sum(sats(o['value']) for o in tx['vout'] if sats(o['value']) == 330)
        match = [o for o in tx['vout'] if sats(o['value']) == expected]
        require(len(match) == 1, 'restored_channel_allocation_mismatch')
        owned.add((closeid, match[0]['n']))
    # Follow any onchaind sweep from the two allocated outputs to the restored wallet.
    for tx in confirmed:
        if tx['txid'] in withdrawals: continue
        ins = {(i.get('txid'), i.get('vout')) for i in tx['vin']}
        if not ins.intersection(owned): continue
        require(ins <= owned, 'mixed_external_input_in_restored_claim')
        owned -= ins
        owned.update((tx['txid'], o['n']) for o in tx['vout'] if sats(o['value']))
    require(owned == set(returned), 'restored_channel_proceeds_not_returned_to_owner')
    # Unspent 330-sat commitment anchors are accounted explicitly, never reported as recovered.
    require(len(unspent) <= 4 and all(k[0] in closing.values() and v == 330 and
            residue[k].startswith('0020') for k, v in unspent.items()), 'unrecovered_nonanchor_funds')
    total = sum(d['sats'] for d in deposits)
    require(total == received+fees+sum(unspent.values()), 'funds_reconciliation_failed')
    require(received > 1300000 and 0 < fees < 50000, 'recovery_value_out_of_bounds')
    result = dict(schema=1, fixture='packaged-xbt-recovery-0088', regtest_only=True, installer=False,
        channels=2, channel_roles=['opener', 'recipient'], original_identity=True,
        database_excluded=True, exact_package_hooks=True, exact_package_commands=True,
        post_backup_payments=2, interrupted_recovery=True, repeated_emergency_recovery=True, high_address_negative_control=True,
        high_address_types=['bech32', 'p2tr'], address_window=10000, full_rescan=True,
        channels_terminal=True, resolved_restart=True, ui_password_and_withdrawal=True,
        unified_withdrawals=3, default_fee_withdrawals=3, deposited_sats=total, drained_sats=received,
        mining_fees_sats=fees, unspent_anchor_sats=sum(unspent.values()),
        startos_supervisor_tested=False, live_migration=False)
    (lab.root/'accounting.json').write_text(json.dumps(dict(deposits=deposits, funding=sorted(funding),
        closing=closing, original_channel_balances=balances, withdrawals=withdrawals,
        remaining_anchors=[dict(txid=k[0], vout=k[1], sats=v) for k, v in unspent.items()]), indent=2)+'\n')
    (lab.root/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    lab.checkpoint('complete')
    print('BACKUP RECOVERY PASSED: 0088; two channel roles, interrupted recovery, high-address rescan and unified withdrawals; no installer', flush=True)


def engine_preflight(results):
    root = Path('/usr/local/share/xbt-cln')
    lock = json.loads((root/'source-lock.json').read_text())
    proof = root/'recovery-fees'
    version = lock['engine_patch']['version']
    require(version == 'v26.06.9-blake2b.7-swap0088b', 'unexpected_recovery_engine')
    expected = (proof/'engine.sha256').read_text().split()
    require(len(expected) == 2 and expected[1] == 'usr/local/bin/lightningd' and
            digest(Path('/usr/local/bin/lightningd')) == expected[0], 'recovery_engine_binary_changed')
    records = {}
    for name, terminal in [('baseline', 'BASELINE: all seven recovery witnesses underestimated'),
                           ('patched', 'PATCHED: all seven recovery witnesses covered')]:
        lines = (proof/(name+'-recovery-weight.txt')).read_text().splitlines()
        require(len(lines) == 8 and lines[-1] == terminal, 'recovery_weight_control_missing_'+name)
        rows = []
        for line in lines[:-1]:
            match = re.fullmatch(r'csv=(\d+) script=(\d+) signature=(\d+) actual=(\d+) estimated=(\d+)', line)
            require(match is not None, 'invalid_recovery_weight_control')
            csv, script, signature, actual, estimate = map(int, match.groups())
            require(37 <= script <= 39 and 69 <= signature <= 71 and
                    actual == 164+1+1+signature+1+script, 'invalid_serialized_witness_weight')
            require((estimate < actual) if name == 'baseline' else (estimate >= actual),
                    'recovery_weight_control_wrong_result')
            rows.append(dict(csv=csv,script=script,signature=signature,actual=actual,estimated=estimate))
        require([r['csv'] for r in rows] == [1,16,17,127,128,4032,32767], 'recovery_weight_matrix_changed')
        records[name] = rows
    value = dict(engine_patch=lock['engine_patch'],binary_sha256=expected[0],controls=records)
    (results/'engine-fix.json').write_text(json.dumps(value, indent=2)+'\n')
    print('PASS: original estimator undercounts; patched estimator covers all seven signed recovery witnesses', flush=True)


def main():
    p = argparse.ArgumentParser(); p.add_argument('--disposable-regtest', action='store_true', required=True)
    p.add_argument('--bitcoind', type=Path, required=True)
    p.add_argument('--bitcoin-cli', type=Path, default=Path('/usr/bin/bitcoin-cli'))
    p.add_argument('--btc-prefix', type=Path, default=Path('/opt/btc'))
    p.add_argument('--xbt-prefix', type=Path, default=Path('/usr/local'))
    p.add_argument('--results-parent', type=Path, required=True)
    args = p.parse_args(); os.umask(0o077); engine_preflight(args.results_parent); lab = RecoveryLab(args)
    try: run(lab)
    finally: lab.close()


if __name__ == '__main__': main()
