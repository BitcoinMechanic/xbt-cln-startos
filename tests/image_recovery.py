"""Disposable packaged-image recovery test. Run via scripts/test-image-recovery.sh.

No production data, external peers or restored database. Requires a surviving
peer and tests a settled channel only; not a StartOS funded-backup approval.
"""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import sys
sys.path.insert(0, "/recovery")
import recovery


def check(condition, message):
    if not condition:
        raise RuntimeError(message)


def rpc(cli, *args):
    result = subprocess.run([*cli, *map(str, args)], capture_output=True,
                            text=True, timeout=60)
    if result.returncode:
        raise RuntimeError(
            f"RPC {args[0]} failed: {result.stdout.strip()} {result.stderr.strip()}"
        )
    output = result.stdout.strip()
    if not output:
        return None
    try:
        return json.loads(output)
    except json.JSONDecodeError:
        if Path(cli[0]).name == 'bitcoin-cli':
            return output
        raise


def wait(fn, label, processes, timeout=120):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        check(all(p.poll() is None for p in processes), f'Process exited: {label}')
        try:
            value = fn()
            if value:
                return value
        except (subprocess.SubprocessError, OSError, ValueError, KeyError, RuntimeError):
            pass
        time.sleep(0.2)
    raise RuntimeError(f'Timed out: {label}')


def main():
    check(os.environ.get('XBT_DISPOSABLE_CONTAINER') == '1', 'Use the Docker launcher')
    os.umask(0o077)
    root = Path(tempfile.mkdtemp(prefix='image-recovery-', dir='/results'))
    print(f'Test directory: {root}', flush=True)
    processes, logs = [], []

    def start(name, args):
        log = (root / f'{name}.log').open('w')
        logs.append(log)
        p = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT)
        processes.append(p)
        return p

    def until(fn, label):
        return wait(fn, label, processes)

    try:
        version = subprocess.check_output(['lightningd', '--version'], text=True).strip()
        check(version == 'xbt-81ba4099a63e', 'Unexpected packaged CLN source version')
        data = root / 'knots'
        data.mkdir()
        start('knots', ['/test-bitcoind', f'-datadir={data}', '-conf=/dev/null',
                       '-regtest', '-server=1', '-listen=0', '-dnsseed=0',
                       '-discover=0', '-connect=0', '-rpcbind=127.0.0.1',
                       '-rpcallowip=127.0.0.1', '-rpcport=18443',
                       '-fallbackfee=0.00001', '-rejectparasites=0',
                       '-testactivationheight=blake2b@1', '-rdtsexpiry=2147483647',
                       '-blake2b_headline=Disposable packaged recovery test'])
        btc = ['bitcoin-cli', f'-datadir={data}', '-regtest', '-rpcport=18443']
        until(lambda: rpc(btc, 'getblockchaininfo'), 'backend RPC')
        rpc(btc, 'createwallet', 'fixture')
        mining = rpc(btc, 'getnewaddress')
        rpc(btc, 'generatetoaddress', 2000 if sys.argv[1:] == ['--empty-scan'] else 101, mining)
        active = []

        def node(name, port, restore=False):
            directory = root / name
            directory.mkdir(exist_ok=True)
            args = ['lightningd', f'--lightning-dir={directory}', '--conf=/dev/null',
                    '--network=xbt-regtest', '--bitcoin-cli=/usr/bin/bitcoin-cli',
                    f'--bitcoin-datadir={data}', '--bitcoin-rpcport=18443',
                    '--developer', '--dev-bitcoind-poll=1', '--disable-dns',
                    '--disable-plugin=cln-grpc',
                    '--autoconnect-seeker-peers=0', '--autolisten=false',
                    f'--bind-addr=127.0.0.1:{port}', '--log-level=debug']
            if restore:
                intent = recovery.load(directory, recovery.INTENT)
                args.append(f"--rescan=-{intent.get('scan_start', 1)}")
            proc = start(name, args)
            cli = ['lightning-cli', f'--lightning-dir={directory}',
                   '--network=xbt-regtest', '--json', '--notifications=none']
            info = until(lambda: rpc(cli, 'getinfo'), f'{name} RPC')
            check(info['network'] == 'xbt-regtest', 'Unexpected network')
            def listening():
                with socket.create_connection(('127.0.0.1', port), timeout=1):
                    return True
            until(listening, f'{name} peer listener')
            active.append(cli)
            return cli, proc, info['id']

        def mine(count):
            blocks = rpc(btc, 'generatetoaddress', count, mining)
            height = rpc(btc, 'getblockcount')
            for cli in active:
                until(lambda: rpc(cli, 'getinfo')['blockheight'] >= height, 'block sync')
            return blocks

        alice, original, identity = node('alice', 19735)
        bob, _, bob_id = node('bob', 19736)
        if sys.argv[1:] == ['--wallet-actions']:
            from wallet_actions import Wallet
            wallet = Wallet(root / 'alice', 'xbt-regtest')
            until(lambda: not any(k.startswith('warning_') for k in rpc(alice, 'getinfo')), 'pilot node sync')
            address = wallet.execute('address')['address']
            check(wallet.execute('address')['address'] == address, 'Deposit address not reused')
            rpc(btc, 'sendtoaddress', address, '0.0005')
            mine(1)
            until(lambda: wallet.execute('funds')['confirmed_unreserved_sats'] == 50000, 'pilot confirmed deposit')
            destination = rpc(bob, 'newaddr', 'p2tr')['p2tr']
            prepared = wallet.execute('prepare', destination=destination, fee_rate=2, max_fee_sats=2000)
            state = recovery.load(root / 'alice', 'wallet-pilot-withdrawal.json')
            check(state['txid'] not in rpc(btc, 'getrawmempool'), 'Preparation broadcast unexpectedly')
            decoded = rpc(btc, 'decoderawtransaction', state['unsigned_tx'])
            check(len(decoded['vout']) == 1 and decoded['vout'][0]['scriptPubKey']['address'] == destination,
                  'Prepared destination differs')
            check(prepared['amount_sats'] + prepared['fee_sats'] == 50000, 'Review accounting mismatch')
            check(wallet.execute('prepare', destination=destination, fee_rate=2, max_fee_sats=2000) ==
                  {**prepared, 'automatic_retry': False}, 'Repeat preparation changed review')
            print('PASS: confirmed deposit; exact destination and fee reviewed; repeated preparation did not broadcast', flush=True)
            sent = wallet.execute('send', review_code=prepared['review_code'])
            check(sent['phase'] == 'broadcast', 'Submission failed')
            until(lambda: state['txid'] in rpc(btc, 'getrawmempool'), 'pilot withdrawal broadcast')
            # Fresh helper reconciles the same record and never calls txsend again.
            fresh = Wallet(root / 'alice', 'xbt-regtest')
            check(fresh.execute('send', review_code=prepared['review_code'])['phase'] == 'broadcast', 'Repeat submission changed phase')
            mine(1)
            until(lambda: any(o['txid'] == state['txid'] and o['status'] == 'confirmed'
                              and o['amount_msat'] == prepared['amount_sats'] * 1000
                              for o in rpc(bob, 'listfunds')['outputs']), 'pilot recipient funds')
            check(fresh.execute('status')['phase'] == 'confirmed', 'Withdrawal not confirmed')
            check(fresh.execute('funds')['confirmed_unreserved_sats'] == 0, 'Pilot sweep left funds')
            print('PASS: reviewed withdrawal confirmed in recipient wallet; repeat send did not resend; payer balance zero', flush=True)
            receiver = Wallet(root / 'bob', 'xbt-regtest')
            review = receiver.execute('prepare', destination=address, fee_rate=2, max_fee_sats=2000)
            cancelled = receiver.execute('cancel', review_code=review['review_code'])
            check(cancelled['phase'] == 'cancelled', 'Cancellation failed')
            check(receiver.execute('cancel', review_code=review['review_code'])['phase'] == 'cancelled', 'Cancellation repeat failed')
            check(receiver.execute('funds')['confirmed_unreserved_sats'] == prepared['amount_sats'], 'Cancellation did not release inputs')
            print('PASS: recipient prepared then cancelled a return; confirmed funds unreserved; cancellation repeat safe', flush=True)
            print('Packaged wallet actions OK (regtest; explicit fee; reviewed on-chain sweep)', flush=True)
            return
        if sys.argv[1:] == ['--empty-scan']:
            rpc(alice, 'stop')
            original.wait(timeout=30)
            check(original.returncode == 0, 'Original stop failed')
            processes.remove(original)
            active.remove(alice)
            recovery.capture(root / 'alice', 'xbt-regtest')
            target = root / 'restored' / 'xbt-regtest'
            target.mkdir(parents=True)
            for name in ('hsm_secret', 'emergency.recover'):
                shutil.copyfile(root / 'alice' / 'xbt-regtest' / name, target / name)
            shutil.copyfile(root / 'alice' / recovery.RECEIPT, target.parent / recovery.RECEIPT)
            recovery.restore(target.parent, 'xbt-regtest')
            restored, process, _ = node('restored', 19735, restore=True)
            check(rpc(restored, 'getinfo')['blockheight'] < 1900, 'Fixture scanned too far before stop')
            rpc(restored, 'stop')
            process.wait(timeout=30)
            check(process.returncode == 0, 'Restored stop failed')
            processes.remove(process)
            active.remove(restored)
            database = target / 'lightningd.sqlite3'
            before = database.read_bytes()
            recovery.set_empty_scan_start(target.parent, 1900, True, 'xbt-regtest')
            check(database.read_bytes() == before, 'Scan adjustment modified database')
            restored, process, restored_id = node('restored', 19735, restore=True)
            check(restored_id == identity, 'Identity changed')
            until(lambda: rpc(restored, 'getinfo')['blockheight'] >= 2000, 'short scan sync')
            result = until(lambda: (out if (out := recovery.step(target.parent, 'xbt-regtest'))['phase'] == 'monitoring' else None), 'empty recovery worker')
            check(result['scan_start'] == 1900 and result['expected_channels'] == 0
                  and result['complete'] is False, 'Unexpected empty recovery status')
            print('PASS: never-funded restored database preserved; scan start advanced to 1900; identity unchanged', flush=True)
            recovery.atomic_json(target.parent, recovery.STATUS, {**result, 'checked_at': time.time()})
            rpc(restored, 'stop')
            process.wait(timeout=30)
            check(process.returncode == 0, 'Stop before finish failed')
            processes.remove(process)
            active.remove(restored)
            before = database.read_bytes()
            recovery.finish_empty(target.parent, True, 'xbt-regtest')
            recovery.finish_empty(target.parent, True, 'xbt-regtest')
            check(database.read_bytes() == before, 'Finish modified database')
            restored, process, restored_id = node('restored', 19735)
            check(restored_id == identity, 'Finish changed identity')
            until(lambda: rpc(restored, 'getinfo')['blockheight'] >= 2000, 'finished wallet sync')
            rpc(restored, 'stop')
            process.wait(timeout=30)
            check(process.returncode == 0, 'Finished wallet stop failed')
            processes.remove(process)
            active.remove(restored)
            recovery.capture(target.parent, 'xbt-regtest')
            print('PASS: empty recovery finished; database and identity preserved; restart and new backup succeeded', flush=True)
            print('Empty restore scan and completion OK (real regtest nodes; no wallet/database deletion)', flush=True)
            return
        check(not sys.argv[1:], 'Unknown test mode')
        deposit = rpc(btc, 'sendtoaddress', rpc(alice, 'newaddr', 'bech32')['bech32'], '0.02')
        mine(1)
        until(lambda: any(o['txid'] == deposit and o['status'] == 'confirmed'
                          for o in rpc(alice, 'listfunds')['outputs']), 'deposit')
        rpc(alice, 'connect', bob_id, '127.0.0.1', 19736)
        funding = rpc(alice, 'fundchannel', bob_id, '1000000sat')
        until(lambda: funding['txid'] in rpc(btc, 'getrawmempool'), 'funding broadcast')
        mine(6)
        for cli in active:
            until(lambda: any(c['state'] == 'CHANNELD_NORMAL' for c in
                              rpc(cli, 'listpeerchannels')['channels']), 'channel ready')
        invoice = rpc(bob, 'invoice', '100000000msat', 'recovery-test', 'Disposable test')
        check(rpc(alice, 'pay', invoice['bolt11'])['status'] == 'complete', 'Payment failed')
        check(rpc(bob, 'listinvoices', 'recovery-test')['invoices'][0]['status'] == 'paid',
              'Receiver not paid')
        for cli in active:
            until(lambda: all(not c.get('htlcs') for c in
                              rpc(cli, 'listpeerchannels')['channels']), 'settled HTLCs')
        rpc(alice, 'stop')
        original.wait(timeout=30)
        check(original.returncode == 0, 'Original node did not stop cleanly')
        processes.remove(original)
        active.remove(alice)
        recovery.capture(root / 'alice', 'xbt-regtest')
        target = root / 'restored' / 'xbt-regtest'
        target.mkdir(parents=True)
        for name in ('hsm_secret', 'emergency.recover'):
            source = root / 'alice' / 'xbt-regtest' / name
            check(source.is_file() and source.stat().st_size > 0, 'Missing recovery material')
            shutil.copyfile(source, target / name)
        check(sorted(p.name for p in target.iterdir()) == ['emergency.recover', 'hsm_secret'],
              'Restore must contain only key and channel backup')
        shutil.copyfile(root / 'alice' / recovery.RECEIPT, target.parent / recovery.RECEIPT)
        recovery.restore(target.parent, 'xbt-regtest')
        print('PASS: stopped-wallet receipt and fresh-volume recovery intent verified', flush=True)
        print('PASS: settled funded wallet stopped; only key and SCB copied to fresh directory', flush=True)
        restored, process, restored_id = node('restored', 19735, restore=True)
        check(restored_id == identity, 'Restored identity changed')
        until(lambda: recovery.step(target.parent, 'xbt-regtest')['phase'] == 'monitoring', 'recovery worker import')
        check(recovery.step(target.parent, 'xbt-regtest')['complete'] is False,
              'Worker must not declare funds recovered')
        print('PASS: recovery worker imported original channel; repeat step reconciled without declaring completion', flush=True)
        # Recovery may already have connected automatically using its stored address.
        rpc(restored, 'connect', bob_id, '127.0.0.1', 19736)
        until(lambda: rpc(btc, 'getrawmempool'), 'peer recovery close')
        block = rpc(btc, 'getblock', mine(1)[0], 2)
        commitments = [tx for tx in block['tx'] if any(
            v.get('txid') == funding['txid'] and v.get('vout') == funding['outnum']
            for v in tx['vin'])]
        check(len(commitments) == 1, 'No unique close spending original funding output')
        commitment = commitments[0]['txid']
        mine(5)
        until(lambda: any(o['txid'] == commitment and o['status'] == 'confirmed'
                          for o in rpc(restored, 'listfunds')['outputs']), 'recovered channel output')
        print('PASS: surviving peer closed original channel; restored wallet owns confirmed close output', flush=True)
        withdrawal = rpc(restored, 'withdraw', rpc(bob, 'newaddr', 'bech32')['bech32'], 'all', '2000perkb')
        tx = rpc(btc, 'decoderawtransaction', withdrawal['tx'])
        check(any(v['txid'] == commitment for v in tx['vin']), 'Withdrawal omitted recovered channel funds')
        until(lambda: withdrawal['txid'] in rpc(btc, 'getrawmempool'), 'recovery withdrawal')
        mine(1)
        until(lambda: any(o['txid'] == withdrawal['txid'] and o['status'] == 'confirmed'
                          for o in rpc(bob, 'listfunds')['outputs']), 'withdrawal confirmed')
        print('PASS: recovered channel funds spent and confirmed in peer wallet', flush=True)
        print('Packaged XBT recovery OK (regtest; surviving peer; no pending HTLCs)', flush=True)
    finally:
        for p in reversed(processes):
            if p.poll() is None:
                p.terminate()
                try:
                    p.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    p.kill()
                    p.wait()
        for log in logs:
            log.close()


if __name__ == '__main__':
    main()
