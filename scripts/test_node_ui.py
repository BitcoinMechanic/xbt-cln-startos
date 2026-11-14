#!/usr/bin/env python3
"""Packaged XBT engine + built web server; fresh isolated regtest only."""
import argparse
import http.client
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import sys

sys.path.insert(0, '/usr/local/libexec/xbt-swap')
import chain_identity as ci
from test_engine import Lab, require, check_received, plugins_ready


class NodeLab(Lab):
    engine_versions = {ci.BTC: ('v26.06.9-swap0070', '26.06.9-swap0070'),
                       ci.PRIVKEYIO_XBT: ('v26.06.9-blake2b.7-swap0086', '26.06.9-blake2b.7-swap0086')}

    def __init__(self, args):
        super().__init__(args); self.rest={}; self.grpc={}

    def start(self, command, log):
        if str(command[0]) == '/usr/local/bin/lightningd':
            name=log.parent.name
            self.rest.setdefault(name,self.port()); self.grpc.setdefault(name,self.port())
            enabled={'pay','cln-xpay','cln-askrene','bookkeeper','sql','chanbackup','clnrest','cln-grpc','commando','keysend','recover'}
            command=[a for a in command if not(str(a).startswith('--disable-plugin=') and str(a).split('=',1)[1] in enabled)]
            command += ['--clnrest-host=127.0.0.1','--clnrest-protocol=http',
                        '--clnrest-port='+str(self.rest[name]),'--grpc-host=127.0.0.1',
                        '--grpc-port='+str(self.grpc[name]),'--xpay-handle-pay=true']
        return super().start(command,log)

    def lightning(self,*args,**kwargs):
        n=super().lightning(*args,**kwargs)
        if n is not None and n['root'].name in self.rest:
            needed={'clnrest','cln-grpc','cln-askrene','cln-xpay','sql','bookkeeper','chanbackup'}
            self.wait(lambda:needed <= {Path(x['name']).name for x in self.rpc(n['cli'],'plugin','list')['plugins'] if x.get('active') is True},n['proc'])
            self.wait(lambda: self.http_ready(n),n['proc'])
        return n

    def http_ready(self,n):
        c=http.client.HTTPConnection('127.0.0.1',self.rest[n['root'].name],timeout=2)
        try:
            c.request('POST','/v1/getinfo',body='{}',headers={'Content-Type':'application/json'})
            r=c.getresponse();r.read();return r.status in (401,403)
        finally:c.close()


class Ui:
    def __init__(self,lab,node):
        self.lab,self.node=lab,node;self.cookies={};self.csrf=None
        self.root=node['root']/'ui';self.root.mkdir(exist_ok=True)
        self.port=lab.port()
        self.password='Disposable-regtest-0086-password'
        self.config=self.root/'config.json'
        fresh=not self.config.exists()
        if fresh:self.config.write_text(json.dumps(dict(unit='SATS',fiatUnit='USD',appMode='DARK',password='')))
        rune=lab.rpc(node['cli'],'createrune')['rune']
        envfile=self.root/'node.env'
        envfile.write_text('LIGHTNING_PUBKEY="'+node['identity']['node_id']+'"\nLIGHTNING_RUNE="'+rune+'"\n')
        env=dict(APP_CONNECT='REST',APP_HOST='127.0.0.1',APP_PORT=str(self.port),APP_PROTOCOL='http',
                 APP_CONFIG_FILE=str(self.config),APP_LOG_FILE=str(self.root/'app.log'),
                 LIGHTNING_VARS_FILE=str(envfile),LIGHTNING_DATA_DIR=str(node['root']),
                 LIGHTNING_REST_HOST='127.0.0.1',LIGHTNING_REST_PORT=str(lab.rest[node['root'].name]),
                 LIGHTNING_REST_PROTOCOL='http',BITCOIN_NETWORK='regtest')
        self.proc=lab.start(['env',*[k+'='+v for k,v in env.items()],'/usr/local/bin/node','/app/apps/backend/dist/server.js'],self.root/'console.log')
        lab.wait(lambda:self.request('GET','/v1/shared/csrf/')[0]==200,self.proc)
        status,reply=self.request('GET','/v1/shared/csrf/');require(status==200,'ui_csrf_unavailable');self.csrf=reply['csrfToken']
        require(self.request('POST','/v1/cln/call',dict(method='getinfo',params={}),token=False)[0]==403,'ui_csrf_not_enforced')
        require(self.request('POST','/v1/cln/call',dict(method='getinfo',params={}))[0]==401,'ui_auth_not_enforced')
        endpoint='/v1/auth/reset/' if fresh else '/v1/auth/login/'
        body=dict(newPassword=self.password,currPassword='') if fresh else dict(password=self.password)
        status,reply=self.request('POST',endpoint,body);require(status==201 and reply['isAuthenticated'] is True,'ui_login_failed')
        status,reply=self.request('GET','/v1/shared/rate/USD');require(status==200 and reply==dict(rate=0,available=False),'ui_uses_BTC_fiat_price')
        status,html=self.request('GET','/');require(status==200 and '<html' in html,'ui_static_assets_missing')

    def request(self,method,path,body=None,*,token=True):
        conn=http.client.HTTPConnection('127.0.0.1',self.port,timeout=90)
        headers={'Content-Type':'application/json','Cookie':'; '.join(k+'='+v for k,v in self.cookies.items())}
        if token and self.csrf:headers['X-XSRF-TOKEN']=self.csrf
        try:
            conn.request(method,path,json.dumps(body) if body is not None else None,headers)
            response=conn.getresponse();data=response.read().decode()
            for k,v in response.getheaders():
                if k.lower()=='set-cookie':
                    cookies=SimpleCookie();cookies.load(v)
                    self.cookies.update({key:val.value for key,val in cookies.items()})
            try:value=json.loads(data)
            except json.JSONDecodeError:value=data
            return response.status,value
        finally:conn.close()

    def rpc(self,method,**params):
        status,reply=self.request('POST','/v1/cln/call',dict(method=method,params=params))
        require(status==200,'ui_rpc_failed_'+method+'_'+str(status))
        return reply


def run(lab):
    lab.checkpoint('packaged-node-startup')
    btc=lab.backend('btc-chain',False); xbt=lab.backend('xbt-chain',True)
    foreign=lab.lightning('btc',ci.BTC,btc)
    lab.lightning('wrong-backend',ci.PRIVKEYIO_XBT,btc,expect_refusal=True)
    payer=lab.lightning('payer',ci.PRIVKEYIO_XBT,xbt);peer=lab.lightning('peer',ci.PRIVKEYIO_XBT,xbt)
    ui=Ui(lab,payer);other=Ui(lab,peer)
    ci.node(ui.rpc('getinfo'),ci.PRIVKEYIO_XBT,'regtest')
    ui.rpc('sql',query='SELECT * FROM peerchannels LIMIT 1')
    ui.rpc('feerates',style='perkw')
    bad=lab.rpc(foreign['cli'],'invoice',1000000,'foreign','wrong chain')['bolt11']
    before=lab.rpc(payer['cli'],'listsendpays')
    status,_=ui.request('POST','/v1/cln/call',dict(method='pay',params=dict(bolt11=bad)))
    require(status>=400 and lab.rpc(payer['cli'],'listsendpays')==before,'foreign_invoice_reached_payment')
    lab.checkpoint('fund-through-ui-address')
    address=ui.rpc('newaddr',addresstype='bech32')['bech32']
    lab.rpc(xbt['cli'],'sendtoaddress',address,'0.01');lab.mine(xbt);lab.synced(xbt,payer,peer)
    lab.wait(lambda:any(x['status']=='confirmed' for x in ui.rpc('listfunds')['outputs']),payer['proc'])
    lab.rpc(payer['cli'],'connect',peer['identity']['node_id'],'127.0.0.1',peer['port'])
    opening=ui.rpc('fundchannel',id=peer['identity']['node_id'],amount=300000,push_msat=50000000)
    lab.mine(xbt);lab.synced(xbt,payer,peer)
    def normal(n):
        rows=lab.rpc(n['cli'],'listpeerchannels')['channels']
        if len(rows)==1 and rows[0]['state']=='CHANNELD_NORMAL' and rows[0]['peer_connected'] and rows[0].get('reestablished'):
            return ci.channel(rows[0],ci.PRIVKEYIO_XBT)
    original=lab.wait(lambda:normal(payer),payer['proc']);lab.wait(lambda:normal(peer),peer['proc'])
    def payment(label,sender,receiver,recipient):
        invoice=receiver.rpc('invoice',amount_msat=1000000,label=label,description='Disposable UI fixture')
        ci.invoice(sender.rpc('decode',string=invoice['bolt11']),ci.PRIVKEYIO_XBT,'regtest')
        result=sender.rpc('pay',bolt11=invoice['bolt11'])
        require(result.get('status')=='complete','ui_payment_incomplete')
        check_received(lab.rpc(recipient['cli'],'listinvoices',label),invoice['payment_hash'],1000000)
        for n in (payer,peer):lab.wait(lambda n=n:(r:=normal(n)) is not None and r.get('htlcs')==[],n['proc'])
    lab.checkpoint('ui-payments-before-restart')
    payment('before',ui,other,peer);payment('return-before',other,ui,payer)
    identities=(payer['identity'],peer['identity'])
    for p in (ui.proc,other.proc,payer['proc'],peer['proc']):lab.stop(p)
    lab.checkpoint('packaged-node-and-ui-restart')
    payer=lab.lightning('payer',ci.PRIVKEYIO_XBT,xbt);peer=lab.lightning('peer',ci.PRIVKEYIO_XBT,xbt)
    lab.rpc(payer['cli'],'connect',peer['identity']['node_id'],'127.0.0.1',peer['port'])
    lab.wait(lambda:normal(payer),payer['proc']);lab.wait(lambda:normal(peer),peer['proc'])
    require((payer['identity'],peer['identity'])==identities,'node_identity_changed')
    current=normal(payer)
    require(current['funding_txid']==original['funding_txid'] and current['channel_type']==original['channel_type'],'funding_or_signing_changed')
    ui=Ui(lab,payer);other=Ui(lab,peer)
    payment('after',ui,other,peer);payment('return-after',other,ui,payer)
    lab.checkpoint('complete')
    result=dict(schema=1,fixture='packaged-xbt-ui-0086',regtest_only=True,installer=False,
                native_rest_and_grpc=True,ui_auth_and_csrf=True,foreign_invoice_refused=True,
                ui_address_and_channel=True,ui_payments=4,original_funding_and_signing=True,
                node_and_ui_restart=True,full_backup_recovery=False,live_migration=False)
    (lab.root/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PACKAGED NODE/UI PASSED: 0086; four payments, original unified channel and node/UI restart; no installer',flush=True)


def main():
    p=argparse.ArgumentParser();p.add_argument('--disposable-regtest',action='store_true',required=True)
    p.add_argument('--bitcoind',type=Path,required=True);p.add_argument('--bitcoin-cli',type=Path,default=Path('/usr/bin/bitcoin-cli'))
    p.add_argument('--btc-prefix',type=Path,default=Path('/opt/btc'));p.add_argument('--xbt-prefix',type=Path,default=Path('/usr/local'))
    p.add_argument('--results-parent',type=Path,required=True);args=p.parse_args()
    os.umask(0o077);lab=NodeLab(args)
    try:run(lab)
    finally:lab.close()

if __name__=='__main__':main()
