const assert = require('node:assert/strict')
const fs = require('node:fs')
const vm = require('node:vm')
const ts = require('typescript')
function load(file, modules) {
 const code=ts.transpileModule(fs.readFileSync(file,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
 const exports={};vm.runInNewContext(code,{exports,require:name=>{assert.ok(name in modules,name);return modules[name]}});return exports
}
async function run() {
 let options,restore,command,stdin
 const events=[],actions={}
 let failed=false
 const chain={setOptions:x=>{options=x;return chain},setPreBackup:()=>chain,setPostRestore:fn=>{restore=fn;return chain}}
 const sdk={setupBackups:fn=>{fn();return {}},Backups:{ofVolumes:()=>chain},volumes:{main:{subpath:name=>'/volume/'+name}},
   SubContainer:{withTemp:async(_e,_i,_m,_n,fn)=>fn({exec:async(cmd,opt)=>{command=cmd;stdin=opt;events.push('recovery');return {exitCode:failed?1:0,stdout:'{"configured":true,"payment_started":false}'}}})},
   Value:{toggle:x=>x},InputSpec:{of:x=>x},Action:{withInput:(id,meta,spec,prefill,handler)=>actions[id]={meta,spec,handler}}}
 const modules={'./sdk':{sdk},'./utils':{mainMounts:{},rootDir:'/volume'},'@start9labs/start-sdk':{},
   'fs/promises':{writeFile:async(path)=>{assert.equal(path,'/volume/xbt-gate-restored.json');events.push('barrier')},
     unlink:async(path)=>{assert.equal(path,'/volume/xbt-gate-activation.json');events.push('unlink')}}}
 load('startos/backups.ts',modules)
 assert.ok(options.exclude.includes('xbt-gate-activation.json'))
 assert.ok(!options.exclude.some(x=>x.includes('swap-gate')))
 await restore({});assert.deepEqual(events,['barrier','unlink','recovery'])
 assert.equal(command.at(-2),'restore')
 events.length=0;failed=true;await assert.rejects(restore({}));assert.deepEqual(events,['barrier','unlink','recovery'])
 failed=false
 load('startos/actions/gate.ts',{'../sdk':{sdk},'../utils':{mainMounts:{},rootDir:'/volume'},'@start9labs/start-sdk':{}})
 assert.equal(actions['xbt-gate-activate'].spec.confirmed.default,false)
 await actions['xbt-gate-activate'].handler({effects:{},input:{confirmed:true}})
 assert.deepEqual(Array.from(command),['/opt/xbt-venv/bin/python','/usr/local/libexec/gate.py','activate','/volume'])
 assert.deepEqual(JSON.parse(stdin.input),{confirmed:true})
 console.log('XBT gate action and restore barrier ordering OK')
}
run().catch(e=>{console.error(e);process.exit(1)})
