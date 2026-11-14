/* Locked compiler; source never borrows a tower credential. */
const fs=require('node:fs'),{spawnSync}=require('node:child_process')
const asset=process.argv[2],phase=process.argv[3]||'compile'
if(!['btc','xbt','controller'].includes(asset)||!['compile','pack'].includes(phase))throw Error('compiler arguments refused')
Object.assign(process.env,{GIT_CONFIG_GLOBAL:'/dev/null',GIT_CONFIG_NOSYSTEM:'1',GIT_TERMINAL_PROMPT:'0',GIT_CONFIG_COUNT:'2',
 GIT_CONFIG_KEY_0:'url.https://github.com/Start9Labs/.insteadOf',GIT_CONFIG_VALUE_0:'ssh://git@github.com/Start9Labs/',
 GIT_CONFIG_KEY_1:'url.https://github.com/Start9Labs/.insteadOf',GIT_CONFIG_VALUE_1:'git@github.com:Start9Labs/'})
function run(argv){const p=spawnSync(argv[0],argv.slice(1),{stdio:'inherit'});if(p.error||p.status!==0)throw Error('compile failed: '+argv[0])}
if(phase==='compile')run(['npm','ci','--ignore-scripts','--no-audit','--no-fund','--cache','/tmp/npm-cache'])
if(require('./node_modules/@start9labs/start-sdk/package.json').version!=='2.0.9')throw Error('SDK version differs')
run(['./node_modules/.bin/tsc','--noEmit'])
if(asset==='xbt'&&phase==='compile')run(['node','scripts/test-package.cjs'])
const entries=phase==='pack'?{javascript:'startos/index.ts'}:{
 regression:'startos/migration/'+(asset==='controller'?'candidate.ts':'actions.ts'),
 live:'startos/live/'+(asset==='controller'?'candidate.ts':'actions.ts')}
for(const [name,entry] of Object.entries(entries))run(['./node_modules/.bin/ncc','build',entry,'-o',name,'--no-cache'])
fs.writeFileSync(phase+'-result.json',JSON.stringify({node:process.version,sdk:require('./node_modules/@start9labs/start-sdk/package.json').version,
 typescript:require('./node_modules/typescript/package.json').version,ncc:require('./node_modules/@vercel/ncc/package.json').version,
 entries,full_typecheck:true})+'\n')
