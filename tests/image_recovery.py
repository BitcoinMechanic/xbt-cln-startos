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
        rpc(btc, 'generatetoaddress', 101, mining)
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
                args.append('--rescan=-1')
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
        target = root / 'restored' / 'xbt-regtest'
        target.mkdir(parents=True)
        for name in ('hsm_secret', 'emergency.recover'):
            source = root / 'alice' / 'xbt-regtest' / name
            check(source.is_file() and source.stat().st_size > 0, 'Missing recovery material')
            shutil.copyfile(source, target / name)
        check(sorted(p.name for p in target.iterdir()) == ['emergency.recover', 'hsm_secret'],
              'Restore must contain only key and channel backup')
        print('PASS: settled funded wallet stopped; only key and SCB copied to fresh directory', flush=True)
        restored, _, restored_id = node('restored', 19735, restore=True)
        check(restored_id == identity, 'Restored identity changed')
        check(funding['channel_id'] in rpc(restored, 'emergencyrecover')['stubs'],
              'Original channel stub not recovered')
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
