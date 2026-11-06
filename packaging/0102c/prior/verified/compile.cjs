/* Locked, isolated source compilation inside the existing pinned Node image. */
const fs=require('node:fs'),{spawnSync}=require('node:child_process')
const entry=process.argv[2]
if(!['startos/migration/actions.ts','startos/migration/candidate.ts'].includes(entry))throw Error('entry refused')
// The pinned public dependency commits use SSH spellings in package-lock.
// Fetch those same commits over HTTPS without borrowing tower credentials or
// changing any user's Git configuration. Scope the rewrite to Start9Labs.
Object.assign(process.env,{GIT_CONFIG_GLOBAL:'/dev/null',GIT_CONFIG_NOSYSTEM:'1',GIT_TERMINAL_PROMPT:'0',GIT_CONFIG_COUNT:'2',
  GIT_CONFIG_KEY_0:'url.https://github.com/Start9Labs/.insteadOf',GIT_CONFIG_VALUE_0:'ssh://git@github.com/Start9Labs/',
  GIT_CONFIG_KEY_1:'url.https://github.com/Start9Labs/.insteadOf',GIT_CONFIG_VALUE_1:'git@github.com:Start9Labs/'})
function run(argv){const p=spawnSync(argv[0],argv.slice(1),{stdio:'inherit'});if(p.error||p.status!==0)throw Error('compile command failed: '+argv[0])}
run(['npm','ci','--ignore-scripts','--no-audit','--no-fund','--cache','/tmp/npm-cache'])
if(require('./node_modules/@start9labs/start-sdk/package.json').version!=='2.0.9')throw Error('SDK version differs')
run(['./node_modules/.bin/tsc','--noEmit'])
run(['./node_modules/.bin/ncc','build',entry,'-o','compiled'])
fs.writeFileSync('compile-result.json',JSON.stringify({node:process.version,sdk:require('./node_modules/@start9labs/start-sdk/package.json').version,
  typescript:require('./node_modules/typescript/package.json').version,ncc:require('./node_modules/@vercel/ncc/package.json').version,
  entry,full_typecheck:true})+'\n')
