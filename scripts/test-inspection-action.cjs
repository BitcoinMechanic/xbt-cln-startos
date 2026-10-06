const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')
module.exports = async function () {
  const actions = []; let command, options
  let reply = {exitCode: 0, stdout: '{"phase":"active","rune":"SECRET","unexpected":"PRIVATE"}'}
  const sdk = { Value: {toggle: x=>x}, InputSpec: {of:x=>x},
    Action: {withInput:(id,meta,spec,prefill,handler)=>{const a={id,meta,spec,prefill,handler};actions.push(a);return a}},
    SubContainer: {withTemp:async(e,image,m,n,fn)=>fn({exec:async(cmd,opts)=>{command=cmd;options=opts;return reply}})} }
  const source=ts.transpileModule(fs.readFileSync('startos/actions/inspectionCredential.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
  vm.runInNewContext(source,{exports:{},require:n=>{
    if(n==='../sdk')return {sdk}
    if(n==='../utils')return {mainMounts:{},rootDir:'/data'}
    throw Error(n)
  }})
  assert.deepEqual(actions.map(a=>a.id),['inspection-credential-status','inspection-credential-create','inspection-credential-revoke'])
  const a=actions[1];assert.equal(a.spec.confirmed.default,false);assert.equal(await a.prefill(),undefined)
  const result=await a.handler({effects:{},input:{confirmed:true}})
  assert.ok(command[1].endsWith('/inspection_credential.py'));assert.equal(command[2],'/data')
  assert.deepEqual(JSON.parse(options.input),{operation:'create',confirmed:true})
  assert.equal(JSON.stringify(command).includes('SECRET'),false)
  const rune=result.result.value.find(r=>r.name==='rune');assert.equal(rune.masked,true);assert.equal(rune.copyable,true)
  assert.equal(JSON.stringify(result).includes('PRIVATE'),false)
  reply={exitCode:1,stdout:'{"error":"SECRET"}'}
  await assert.rejects(a.handler({effects:{},input:{confirmed:true}}),e=>!e.message.includes('SECRET'))
  console.log('Inspection credential action confirmation, masking, fixed command and private errors OK')
}
if(require.main===module)module.exports().catch(e=>{console.error(e);process.exit(1)})
