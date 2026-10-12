import assert from 'node:assert/strict';
import { pathToFileURL } from 'node:url';
const root = process.argv[2] || '/app';
const { requireXbtInvoice } = await import(pathToFileURL(root+'/apps/backend/dist/service/lightning.service.js'));
const { validateUiConfig } = await import(pathToFileURL(root+'/apps/backend/dist/controllers/shared.js'));
const { validateCallRequest } = await import(pathToFileURL(root+'/apps/backend/dist/controllers/lightning.js'));
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
