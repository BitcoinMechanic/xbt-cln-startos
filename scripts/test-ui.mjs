import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const root = process.argv[2] || '/app';
const { requireXbtInvoice } = await import(pathToFileURL(root+'/apps/backend/dist/service/lightning.service.js'));
const { validateUiConfig } = await import(pathToFileURL(root+'/apps/backend/dist/controllers/shared.js'));
const { validateCallRequest, peerUiAddresses } = await import(pathToFileURL(root+'/apps/backend/dist/controllers/lightning.js'));
const invoice = {valid:true,type:'bolt11 invoice',currency:'bc',features:(1n<<512n).toString(16).padStart(130,'0')};
requireXbtInvoice(invoice);
for (const bad of [{features:'00'},{features:'f'}, {features:'0x12'}, {valid:false}, {type:'bolt12 invoice'}, {currency:'xbt'}, {features:((1n<<512n)|(1n<<513n)).toString(16).padStart(130,'0')}]) {
  assert.throws(()=>requireXbtInvoice({...invoice,...bad}));
}
assert.equal(validateUiConfig({unit:'XBT',fiatUnit:'USD',appMode:'DARK'}),null);
assert.notEqual(validateUiConfig({unit:'BTC',fiatUnit:'USD',appMode:'DARK'}),null);
assert.equal(validateCallRequest('pay',{bolt11:'test'}),null);
for (const method of ['plugin','sendpay','offer','fetchinvoice']) assert.notEqual(validateCallRequest(method,{}),null);
assert.notEqual(validateCallRequest('pay',[]),null);
console.log('PASS: built UI invoice chain checks, XBT settings and RPC request boundary');

assert.deepEqual(peerUiAddresses(['192.168.8.102:64774','[2001:db8::1]:9735','a'.repeat(56)+'.onion:9735']), [
 {type:'ipv4',address:'192.168.8.102',port:64774},
 {type:'ipv6',address:'2001:db8::1',port:9735},
 {type:'torv3',address:'a'.repeat(56)+'.onion',port:9735}
]);
assert.deepEqual(peerUiAddresses(['0.0.0.0:9735','[::]:9735','127.0.0.1:9735','host:0','host:65536','user:secret@host:9735','host:9735/path','host:9735?secret']), []);
console.log('PASS: reachable peer endpoints, external ports, IPv6, Tor and invalid binding rejection');

const channelId = 'a'.repeat(64);
assert.equal(validateCallRequest('setchannellabel',{channel_id:channelId,label:'Savings'}),null);
assert.equal(validateCallRequest('setchannellabel',{channel_id:channelId,label:''}),null);
for (const params of [{channel_id:'../secret',label:'test'},{channel_id:channelId,label:'x'.repeat(81)},{channel_id:channelId,label:'bad\nlabel'},{channel_id:channelId,label:'test',key:['other']}]) {
  assert.notEqual(validateCallRequest('setchannellabel',params),null);
}
for (const method of ['datastore','deldatastore','listdatastore']) assert.notEqual(validateCallRequest(method,{}),null);
console.log('PASS: channel label validation and private datastore boundary');
const { LightningController } = await import(pathToFileURL(root+'/apps/backend/dist/controllers/lightning.js'));
const savedLabels = new Map();
const calls = [];
const mock = {call: async (method, params) => {
  calls.push([method, params]);
  if (method === 'listpeerchannels') return {channels:[{channel_id:channelId},{channel_id:'b'.repeat(64)}]};
  if (method === 'datastore') { savedLabels.set(params.key[2], params.string); return {}; }
  if (method === 'listdatastore') return {datastore:[...savedLabels].map(([id,string])=>({key:['cln-application','channel-labels',id],string}))};
  throw Error('Unexpected RPC');
}};
async function call(controller, method, params) {
  return new Promise((resolve,reject) => controller.callMethod({body:{method,params}}, {
    status(code) { this.code=code; return this; }, json(body) { resolve({code:this.code,body}); },
  }, reject));
}
let controller = new LightningController(mock);
assert.equal((await call(controller,'setchannellabel',{channel_id:channelId,label:' Savings '})).code,200);
assert.equal(savedLabels.get(channelId),'Savings');
controller = new LightningController(mock); // no process-local label state
let response = await call(controller,'listpeerchannels',{});
assert.equal(response.body.channels[0].channel_label,'Savings');
assert.equal(response.body.channels[1].channel_label,'');
assert.equal((await call(controller,'setchannellabel',{channel_id:channelId,label:''})).code,200);
assert.equal((await call(controller,'listpeerchannels',{})).body.channels[0].channel_label,'');
assert(calls.filter(([method])=>method==='datastore').every(([,p])=>p.key[0]==='cln-application' && p.key[1]==='channel-labels'));
console.log('PASS: labels persist through controller recreation, remain channel-specific and can be cleared');
