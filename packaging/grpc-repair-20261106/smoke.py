import subprocess,json,time,hashlib
from pathlib import Path
o=Path(__file__).resolve().parent
root=o.parents[1]
image=(o/'image.id').read_text().strip()
import tempfile
state=Path(tempfile.mkdtemp(prefix='smoke-state-',dir=o))
backend=state/'backend';backend.mkdir();node=state/'node';node.mkdir()
conf=(o/'generated-config').read_text().replace('network=bitcoin','network=regtest')
(node/'config').write_text(conf)
backend_log=(o/'backend-smoke.log').open('w')
bp=subprocess.Popen([str(root.parent/'bitcoind'),'-regtest','-testactivationheight=blake2b@1',f'-datadir={backend}','-server','-listen=0','-connect=0','-dnsseed=0','-discover=0','-rpcport=19487','-rpcuser=smoketest','-rpcpassword=disposable-regtest-only'],stdout=backend_log,stderr=subprocess.STDOUT)
name='xbt-grpc-repair-smoke-20261106'
def run(args,**kw):return subprocess.run(args,check=True,capture_output=True,text=True,**kw).stdout
def rpc(*args):return json.loads(run(['docker','exec',name,'/opt/xbt/bin/lightning-cli','--lightning-dir=/smoke','--network=regtest',*args]))
try:
 time.sleep(3)
 run(['docker','run','-d','--name',name,'--network','host','-v',f'{node}:/smoke','--entrypoint','/usr/local/libexec/swap-node/package_node.py',image,'--disposable-regtest','--profile','xbt-privkeyio-v1','--root','/smoke','launch','--conf=/smoke/config','--important-plugin=/opt/xbt/libexec/c-lightning/plugins/cln-grpc','--important-plugin=/opt/xbt/libexec/c-lightning/plugins/clnrest','--bitcoin-rpcconnect=127.0.0.1','--bitcoin-rpcport=19487','--bitcoin-rpcuser=smoketest','--bitcoin-rpcpassword=disposable-regtest-only','--bitcoin-datadir=/smoke','--offline'])
 for _ in range(40):
  try:info=rpc('getinfo');break
  except subprocess.CalledProcessError:time.sleep(1)
 else:raise RuntimeError('daemon did not become ready')
 plugins=rpc('plugin','list')
 assert any(x['name'].endswith('/cln-grpc') and x['active'] for x in plugins['plugins']),plugins
 time.sleep(5)
 info2=rpc('getinfo');assert info2['id']==info['id']
 run(['docker','restart',name])
 for _ in range(40):
  try:info3=rpc('getinfo');break
  except subprocess.CalledProcessError:time.sleep(1)
 else:raise RuntimeError('restart failed')
 assert info3['id']==info['id']
 (o/'smoke-result.json').write_text(json.dumps(dict(daemon_ready=True,grpc_plugin_active=True,identity_preserved_on_restart=True,regtest_only=True,funded_payments=False,plugins=plugins),indent=2))
 print('PASS: generated config, active gRPC plugin, daemon RPC, same-volume restart identity')
finally:
 p=subprocess.run(['docker','logs',name],capture_output=True,text=True);(o/'node-smoke.log').write_text(p.stdout+p.stderr)
 subprocess.run(['docker','rm','-f',name],capture_output=True)
 bp.terminate();bp.wait(timeout=30);backend_log.close()
