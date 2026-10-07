const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),ts=require('typescript')
module.exports=async function(){
 const actions=[];let cmd,input
 const sdk={Value:{text:x=>x,toggle:x=>x,number:x=>x},InputSpec:{of:x=>x},Action:{withInput:(id,meta,spec,prefill,handler)=>{const a={id,spec,handler};actions.push(a);return a}},SubContainer:{withTemp:async(e,i,m,n,f)=>f({exec:async(c,o)=>{cmd=c;input=JSON.parse(o.input);return {exitCode:0,stdout:JSON.stringify({credential:'PRIVATE',max_swaps:5})}}})}}
 const js=ts.transpileModule(fs.readFileSync('startos/actions/swapSession.ts','utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
 vm.runInNewContext(js,{exports:{},require:n=>n==='../sdk'?{sdk}:{mainMounts:{},rootDir:'/data'}})
 assert.equal(actions.length,2);assert.equal(actions[0].spec.confirmed.default,false)
 assert.equal(actions[0].spec.newGrant.default,false);assert.equal(actions[0].spec.maxSwaps.min,1);assert.equal(actions[0].spec.maxSwaps.max,10)
 const result=await actions[0].handler({effects:{},input:{channel:null,maxSwaps:5,newGrant:false,confirmed:true}})
 assert.equal(input.channel,'');assert.equal(cmd.at(-1),'enable');assert.ok(cmd[1].endsWith('/swap_session.py'))
 assert.equal(result.result.value.find(x=>x.name==='Controller grant credential').masked,true)
 assert.equal(actions[1].spec.confirmed.default,false)
 console.log('Repeat grant actions: explicit bounded setup, no automatic renewal, private stdin and masked credential OK')
}
if(require.main===module)module.exports().catch(e=>{console.error(e);process.exit(1)})
