#!/usr/bin/env python3
"""Real Paul Knots/proxy and XBT CLN; fresh disposable regtest datadirs only."""
import argparse,json,os,subprocess,time
from pathlib import Path
import chain_identity as ci
from test_engine import Lab as BaseLab,require,funding_address,direct_payment,check_received

class Lab(BaseLab):
    engine_versions={ci.PRIVKEYIO_XBT:('v26.06.9-blake2b.7-swap0094',)}
    def wait(self, fn, proc=None, timeout=300):
        return super().wait(fn,proc,timeout)
    def start(self,command,log):
        if str(command[0])==str(self.args.xbt_prefix/'bin/lightningd') and getattr(self,'rescan',False) and log.parent.name=='source':
            command=[*command,'--rescan=-100']
        return super().start(command,log)
    def backend(self,name,pruned=False,peer=None):
        root=self.root/name;root.mkdir();port=self.port();p2p=self.port()
        command=[self.args.bitcoind,f'-datadir={root}','-conf=/dev/null','-regtest','-server=1',
            '-dnsseed=0','-discover=0',f'-bind=127.0.0.1:{p2p}',f'-port={p2p}',
            '-rpcbind=127.0.0.1','-rpcallowip=127.0.0.1',f'-rpcport={port}',
            '-fallbackfee=0.00001','-rejectparasites=0','-testactivationheight=blake2b@1',
            '-rdtsexpiry=2147483647','-blake2b_headline=Disposable pruned XBT fixture']
        command += ['-prune=1','-fastprune=1'] if pruned else []
        command += [f'-connect=127.0.0.1:{peer["p2p"]}'] if peer else ['-connect=0']
        proc=self.start(command,root/'console.log')
        cli=[self.args.bitcoin_cli,f'-datadir={root}','-conf=/dev/null','-regtest',f'-rpcport={port}']
        self.wait(lambda:self.rpc(cli,'getblockchaininfo'),proc)
        result=dict(root=root,port=port,p2p=p2p,cli=cli,proc=proc,command=command)
        if not pruned:
            self.rpc(cli,'createwallet','fixture');result['address']=self.rpc(cli,'getnewaddress')
            self.mine(result,101)
        else:self.wait(lambda:self.rpc(cli,'getblockcount')==self.rpc(peer['cli'],'getblockcount'),proc)
        return result

def run(lab):
    lab.checkpoint('start-archival-peer-pruned-backend-and-exact-proxy')
    archive=lab.backend('archive');pruned=lab.backend('pruned',True,archive)
    port=lab.port();cookie=pruned['root']/'regtest/.cookie'
    conf=lab.root/'proxy.toml'
    conf.write_text(f'''bitcoind_address = "127.0.0.1"
bitcoind_port = {pruned['port']}
bind_address = "127.0.0.1"
bind_port = {port}
cookie_file = "{cookie}"
passthrough_rpccookie = "{cookie}"
default_fetch_blocks = true
max_peer_concurrency = 1
# Shorten only peer-cache refresh in the disposable outage test.
max_peer_age = 1
peer_timeout = 5
block_cache_size_mib = 1
''')
    proxy_command=[lab.args.proxy,'--conf',conf,'-vv']
    proxy=lab.start(proxy_command,lab.root/'proxy.log')
    backend={**pruned,'port':port,'cli':[lab.args.bitcoin_cli,'-regtest',f'-rpcport={port}',f'-rpccookiefile={cookie}']}
    lab.wait(lambda:lab.rpc(backend['cli'],'getblockchaininfo'),proxy)
    source=lab.lightning('source',ci.PRIVKEYIO_XBT,backend)
    recipient=lab.lightning('recipient',ci.PRIVKEYIO_XBT,archive)
    lab.checkpoint('fund-channel-through-proxy')
    lab.rpc(archive['cli'],'sendtoaddress',funding_address(lab,source),'0.01')
    lab.mine(archive);lab.synced(archive,source,recipient)
    lab.wait(lambda:any(o['status']=='confirmed' for o in lab.rpc(source['cli'],'listfunds')['outputs']),source['proc'])
    lab.rpc(source['cli'],'connect',recipient['identity']['node_id'],'127.0.0.1',recipient['port'])
    opened=lab.rpc(source['cli'],'fundchannel',recipient['identity']['node_id'],300000,timeout=90)
    lab.wait(lambda:opened['txid'] in lab.rpc(archive['cli'],'getrawmempool'),archive['proc'])
    lab.mine(archive);lab.synced(archive,source,recipient)
    def normal(n):
        rows=lab.rpc(n['cli'],'listpeerchannels')['channels']
        return rows[0] if len(rows)==1 and rows[0]['state']=='CHANNELD_NORMAL' and rows[0]['peer_connected'] and rows[0].get('reestablished') else None
    original=lab.wait(lambda:normal(source),source['proc'])
    def payment(label):
        c=lab.wait(lambda:normal(source),source['proc']);lab.wait(lambda:normal(recipient),recipient['proc'])
        created=lab.rpc(recipient['cli'],'invoice',1000000,label,'pruned recovery fixture')
        direct_payment(lab,source,recipient,c,created,1000000)
        check_received(lab.rpc(recipient['cli'],'listinvoices',label),created['payment_hash'],1000000)
        lab.wait(lambda:normal(source).get('htlcs')==[],source['proc'])
    payment('before-pruning')
    identity=source['identity'];oldheight=lab.rpc(archive['cli'],'getblockcount')
    oldhash=lab.rpc(archive['cli'],'getblockhash',oldheight)
    raw=lab.rpc(archive['cli'],'getblock',oldhash,0)
    lab.stop(source['proc'])
    lab.checkpoint('offline-lightning-backend-prunes-old-blocks')
    lab.rpc(archive['cli'],'generatetoaddress',600,archive['address'],timeout=600)
    lab.wait(lambda:lab.rpc(pruned['cli'],'getblockcount')==lab.rpc(archive['cli'],'getblockcount'),pruned['proc'])
    lab.rpc(pruned['cli'],'pruneblockchain',500)
    info=lab.rpc(pruned['cli'],'getblockchaininfo')
    require(info['pruned'] and info['pruneheight']>oldheight,'fixture_did_not_actually_prune')
    try:lab.rpc(pruned['cli'],'getblock',oldhash,0)
    except subprocess.CalledProcessError:pass
    else:raise RuntimeError('old_block_still_available_directly')
    # Restart proxy clears its in-memory cache; the peer must supply the bytes.
    lab.stop(proxy);proxy=lab.start(proxy_command,lab.root/'proxy.log')
    lab.wait(lambda:lab.rpc(backend['cli'],'getblockchaininfo'),proxy)
    require(lab.rpc(backend['cli'],'getblock',oldhash,0,timeout=90)==raw,'proxy_pruned_block_mismatch')
    lab.checkpoint('restart-and-rescan-old-channel-through-pruned-proxy')
    lab.rescan=True
    source=lab.lightning('source',ci.PRIVKEYIO_XBT,backend)
    lab.synced(archive,source,recipient)
    lab.rpc(source['cli'],'connect',recipient['identity']['node_id'],'127.0.0.1',recipient['port'])
    recovered=lab.wait(lambda:normal(source),source['proc'])
    ci.same_binding(identity,source['identity'])
    for key in ('channel_id','funding_txid','short_channel_id','channel_type'):
        require(recovered[key]==original[key],'channel_changed_after_pruned_rescan')
    payment('after-pruned-rescan')
    lab.checkpoint('missing-peer-fails-and-peer-restoration-recovers')
    lab.stop(source['proc']);lab.stop(recipient['proc']);lab.stop(archive['proc']);lab.stop(proxy)
    proxy=lab.start(proxy_command,lab.root/'proxy.log');lab.wait(lambda:lab.rpc(backend['cli'],'getblockchaininfo'),proxy)
    try:lab.rpc(backend['cli'],'getblock',oldhash,0,timeout=30)
    except subprocess.CalledProcessError:pass
    else:raise RuntimeError('old_block_available_without_peer_or_cache')
    archive['proc']=lab.start(archive['command'],archive['root']/'console.log')
    lab.wait(lambda:lab.rpc(archive['cli'],'getblockchaininfo'),archive['proc'])
    lab.rpc(pruned['cli'],'addnode',f'127.0.0.1:{archive["p2p"]}','onetry')
    lab.wait(lambda:any(not p['inbound'] and 'NETWORK' in p.get('servicesnames',[])
        for p in lab.rpc(pruned['cli'],'getpeerinfo')),pruned['proc'])
    lab.stop(proxy);proxy=lab.start(proxy_command,lab.root/'proxy.log');lab.wait(lambda:lab.rpc(backend['cli'],'getblockchaininfo'),proxy)
    lab.wait(lambda:lab.rpc(backend['cli'],'getblock',oldhash,0,timeout=30)==raw,proxy)
    result=dict(regtest_only=True,actual_pruning=True,pruneheight=info['pruneheight'],old_block_height=oldheight,
        exact_proxy=True,pruned_block_bytes_match=True,channel_and_identity_preserved=True,rescan=True,
        payments_before_and_after=2,missing_peer_refused=True,peer_restoration_recovered=True)
    (lab.root/'result.json').write_text(json.dumps(result,indent=2)+'\n');lab.checkpoint('complete');print('PASS: real pruned BLAKE2b proxy, funded-channel restart/rescan and peer recovery',flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--disposable-regtest',required=True,action='store_true')
    for k in ('bitcoind','bitcoin-cli','proxy','btc-prefix','xbt-prefix','results-parent'):p.add_argument('--'+k,type=Path,required=True)
    args=p.parse_args();os.umask(0o077);lab=Lab(args)
    try:run(lab)
    finally:lab.close()
