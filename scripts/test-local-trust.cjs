const assert=require('node:assert/strict'),fs=require('node:fs/promises'),syncfs=require('node:fs'),path=require('node:path'),os=require('node:os'),Module=require('node:module'),ts=require('typescript');
function load(file,mocks={}) { const name=path.resolve(file),m=new Module(name,module);m.filename=name;m.paths=module.paths;m.require=n=>n in mocks?mocks[n]:require(n);m._compile(ts.transpileModule(syncfs.readFileSync(name,'utf8'),{compilerOptions:{module:ts.ModuleKind.CommonJS,target:ts.ScriptTarget.ES2022}}).outputText,name);return m.exports }
async function main(){
 const dir=await fs.mkdtemp(path.join(os.tmpdir(),'local-trust-'));
 try {
 let restart=0, action,config=false;const calls=[];
 const sdk={volumes:{main:{subpath:p=>path.join(dir,p)},public:{subpath:p=>path.join(dir,'public',p)}},
  restart:async()=>restart++,Action:{withInput:(id,meta,spec,prefill,run)=>action={id,meta,prefill,run}},InputSpec:{of:x=>x},Value:{toggle:x=>x}};
 const clnConfig={read:()=>({once:async()=>({clnrest:config})}),merge:async()=>{config=true}};
 const mod=load('startos/live/localController.ts',{'../sdk':{sdk},'../utils':{clnrestPort:3010},'../fileModels/config':{clnConfig}});
 const call=async(_,r)=>{calls.push(r);if(r.action==='status')return {blocked:false,reviews:[]};return {state:'waiting',enabled:true,roles:{incoming:'waiting_for_channels',outgoing:'waiting_for_channels'}}};
 mod.localControllerAction('btc-cln-v1',call);
 assert.equal((await action.prefill()).enabled,false);
 await fs.writeFile(path.join(dir,'local-controller-enabled.json'),'{"enabled":true}');
 assert.equal((await action.prefill()).enabled,false);
 await mod.syncLocalController({},'btc-cln-v1',call);
 assert.equal(calls.some(c=>c.action==='local-trust'),false,'legacy sharing must not gain authority');
 calls.length=0;
 await action.run({effects:{},input:{enabled:true}});
 assert.deepEqual(calls,[{action:'setup',confirmed:true},{action:'local-trust',operation:'enable'}]);assert.equal(restart,1);assert.equal(config,true);
 assert.equal((await action.prefill()).enabled,true);
 calls.length=0;await mod.syncLocalController({},'btc-cln-v1',call);
 assert.deepEqual(calls[0],{action:'local-trust',operation:'maintain'});
 const pub=path.join(dir,'public/swap-controller.json');assert.equal(JSON.parse(await fs.readFile(pub,'utf8')).format,'local-swap-node-v1');
 await action.run({effects:{},input:{enabled:false}});assert.deepEqual(calls.at(-1),{action:'local-trust',operation:'disable'});
 assert.equal((await action.prefill()).enabled,false);await assert.rejects(fs.access(pub));
 await action.run({effects:{},input:{enabled:true}});
 await mod.syncLocalController({},'btc-cln-v1',async()=>({state:'paused',enabled:false}));await assert.rejects(fs.access(pub));
 await mod.syncLocalController({},'btc-cln-v1',async()=>{throw Error('private rune')});await assert.rejects(fs.access(pub));
 // The image adapter exposes only a fixed local operation, never arbitrary RPC.
 const stub={...sdk,Action:{withInput:()=>({}),withOutput:()=>({}),of:()=>({})},Value:new Proxy({}, {get:()=>()=>({})})};
 // Test adapter separately without evaluating the unrelated action declarations.
 const source=syncfs.readFileSync('startos/live/actions.ts','utf8');const end=source.indexOf('export const rawInvoke');
 const tmp=path.join(dir,'adapter.ts');await fs.writeFile(tmp,source.slice(0,end));
 const adapter=load(tmp,{'./localController':mod,'../sdk':{sdk:stub},'../utils':{rootDir:'/root/.lightning'},'../volume':{rootDir:'/root/.lightning'}});
 let argv;await adapter.executeRequest({action:'local-trust',operation:'maintain'},async a=>{argv=a;return {exitCode:0,stdout:'{"state":"ready"}'}});
 assert.deepEqual(argv.slice(0,3),['python3','-I','/usr/local/libexec/local-controller-trust.py']);assert.equal(argv.at(-1),'maintain');
 for(const req of [{action:'local-trust',operation:'sendpay'},{action:'local-trust',operation:'enable',rune:'private'}])await assert.rejects(adapter.executeRequest(req,async()=>{throw Error('must not execute')}));
 console.log('PASS: one-time trust, legacy opt-in preservation, maintenance, revocation, failure cleanup and restricted image adapter');
 } finally {await fs.rm(dir,{recursive:true,force:true})}
}
main().catch(e=>{console.error(e);process.exitCode=1});
