const assert = require('node:assert/strict')
const fs = require('node:fs/promises')
const { readFileSync } = require('node:fs')
const path = require('node:path')
const os = require('node:os')
const Module = require('node:module')
const ts = require('typescript')
function load(file, mocks = {}) {
  const filename = path.resolve(file)
  const mod = new Module(filename, module)
  mod.filename = filename; mod.paths = module.paths
  mod.require = name => name in mocks ? mocks[name] : require(name)
  mod._compile(ts.transpileModule(readFileSync(filename, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText, filename)
  return mod.exports
}
async function main() {
  // Presence, not health or bridge availability, selects one consistent backend.
  for (const installed of [false, true]) for (const address of [null, '10.0.3.1:43123', '[fd00:3::1]:43123']) {
    const requests = []
    const backendSdk = {
      getServiceManifest: (_effects, id, map) => {
        assert.equal(id, 'knots-blake2b')
        return {const: async () => map(installed ? {id} : null)}
      },
      host: {getBridgeAddress: (_effects, opts) => {
        requests.push(opts); return {const: async () => address}
      }},
      setupDependencies: f => f,
    }
    const backend = load('startos/backend.ts', {
      './sdk': {sdk: backendSdk},
      'bitcoin-core-startos/startos/utils': {rpcHostId:'rpc', rpcPort:8332},
    })
    const expected = installed ? 'knots-blake2b' : 'bitcoind'
    assert.equal(await backend.selectedBackend({}), expected)
    const connection = await backend.backendRpcBridge({})
    assert.deepEqual(requests, [{packageId:expected,hostId:'rpc',internalPort:installed?18443:8332,ssl:false}])
    if (address) {
      assert.equal(connection.packageId, expected); assert.equal(connection.port,43123)
      assert.equal(connection.host,address.startsWith('[')?'fd00:3::1':'10.0.3.1')
    } else assert.equal(connection,null) // No fallback when preferred binding is missing.
    const dependencies = load('startos/dependencies.ts', {'./sdk':{sdk:backendSdk},'./backend':backend})
    assert.deepEqual(await dependencies.setDependencies({effects:{}}), {
      [expected]: {healthChecks:installed?['node','chain']:['bitcoind','sync-progress'],kind:'running',versionRange:installed?'>=29.4.3:1':'*'},
    })
  }
  const policy = load('startos/xbtPolicy.ts')
  const recovery = load('startos/recovery.ts', {'./xbtPolicy':policy})
  const temp = await fs.mkdtemp(path.join(os.tmpdir(), 'xbt-package-'))
  const root = path.join(temp, 'volume'); await fs.mkdir(root)
  try {
    // Recorded public RPC responses from the real backend that exposed 0090's bug.
    const recorded = JSON.parse(readFileSync('scripts/fixtures/knots-mainnet-20261012.json', 'utf8'))
    const good = recorded.getblockchaininfo
    const dep = recorded.getdeploymentinfo
    assert.equal(recorded.getblockhash, policy.activationHash)
    policy.verifyBackend(good, dep, policy.activationHash)
    for (const override of [{chain:'regtest'}, {pruned:true}, {initialblockdownload:true}, {blocks:0}])
      assert.throws(() => policy.verifyBackend({...good,...override}, dep, policy.activationHash))
    assert.throws(() => policy.verifyBackend(good, {}, policy.activationHash))
    assert.throws(() => policy.verifyBackend(good, dep, '00'.repeat(32)))
    const hex = n => n.toString(16).padStart(130, '0')
    const info = {id:'02'+'11'.repeat(32), network:'bitcoin', blockheight:961700,
      our_features: {init:hex((1n<<512n)|(1n<<515n)), node:hex((1n<<512n)|(1n<<515n)),invoice:hex(1n<<512n)}}
    policy.verifyNode(info)
    assert.throws(() => policy.verifyNode({...info,our_features:{init:'00',node:'00',invoice:'00'}}))
    assert.throws(() => policy.verifyNode({...info,network:'xbt'}))
    await assert.rejects(() => policy.verifyVolume(root))
    await policy.verifyVolume(root, true); await policy.verifyVolume(root)
    await fs.mkdir(path.join(root,'xbt'))
    await assert.rejects(() => policy.verifyVolume(root, true))
    await fs.rmdir(path.join(root,'xbt'))
    await fs.mkdir(path.join(root,'bitcoin'))
    await fs.mkdir(path.join(root,'bitcoin',policy.swapDirs[0]))
    await assert.rejects(() => policy.requireInactiveSwaps(root))
    await fs.rmdir(path.join(root,'bitcoin',policy.swapDirs[0]))
    const missing = path.join(temp,'unrecognized'); await fs.mkdir(missing); await fs.mkdir(path.join(missing,'bitcoin'))
    await assert.rejects(() => policy.verifyVolume(missing,true))
    await fs.unlink(path.join(root,policy.marker))
    await fs.symlink(path.join(missing,'identity'),path.join(root,policy.marker))
    await assert.rejects(() => policy.verifyVolume(root,true))
    await fs.unlink(path.join(root,policy.marker)); await fs.writeFile(path.join(root,policy.marker), JSON.stringify(policy.identity))
    const chain=[]; const flags=[]; const tasks=[]
    let rpcReplies = structuredClone(recorded)
    const rpcCalls = []
    const connection = {host:'127.0.0.1',port:8332,packageId:'bitcoind'}
    const backup = {setOptions(o){this.options=o;return this},setPreBackup(f){this.before=f;return this},setPostRestore(f){this.after=f;return this}}
    const sdk = {
      volumes:{main:{subpath:p=>path.join(root,p)}},
      setupMain:f=>f, setupBackups:f=>({createBackup:f,restoreInit:null}), setHealth:async()=>null,
      Backups:{ofVolumes:()=>backup}, action:{createOwnTask:async(...a)=>tasks.push(a)},
      SubContainer:{of:()=>({rootfs:'/test', exec:async (args,_options,timeout)=>{
        assert.equal(timeout,70000) // The host deadline must allow the proxy RPC's 60 seconds.
        const method=args.find(x=>['getblockchaininfo','getdeploymentinfo','getblockhash','getblock'].includes(x))
        rpcCalls.push({method,args})
        return {exitCode:0,stdout:['getblockhash','getblock'].includes(method)?rpcReplies[method]:JSON.stringify(rpcReplies[method])}
      }})},
      Daemons:{of:()=>({addDaemon(id,spec){chain.push({id,spec});return this},addOneshot(id,spec){chain.push({id,spec});return this},addHealthCheck(id,spec){chain.push({id,spec});return this}})},
    }
    const store={read:()=>({once:async()=>({restore:true,customExternalHosts:[],watchtowerClients:[],watchtowerServer:false}),const:async()=>null}),merge:async(_,v)=>flags.push(v)}
    const mocks={
      './live/localController': {publicationDaemon:()=>({requires:['lightningd']})},
      './live/actions': {profile:'xbt-privkeyio-v1',rawInvoke:async()=>({})},
      '@start9labs/start-sdk':{FileHelper:{string:()=>({read:()=>({const:async()=>null})})}},
      'bitcoin-core-startos/startos/manifest':{manifest:{}},
      './sdk':{sdk},'./xbtPolicy':policy,'./recovery':recovery,'./fileModels/store.json':{storeJson:store},
      './fileModels/config':{clnConfig:{read:()=>({const:async()=>({raw:{plugin:[]}})})}},
      './i18n':{i18n:x=>x},'./utils':{rootDir:'/root/.lightning',bitcoinDataDir:'/mnt/bitcoin',bitcoindRpcBridge:async()=>connection,mainMounts:{mountDependency:()=>null}},
      './actions/watchtower/towerUri':{},'./actions/watchtower/watchtower':{},'./actions/watchtower/watchtowerClientInfo':{},
      './actions/rescanBlockchain':{rescanBlockchain:{}},
    }
    const main = load('startos/main.ts',mocks).main
    await main({effects:{}})
    const ids=[]
    for (const entry of chain) {
      const s=typeof entry.spec==='function'?await entry.spec():entry.spec
      if (!s) continue
      for (const dep of s.requires) assert.ok(ids.includes(dep), `${entry.id} needs earlier ${dep}`)
      ids.push(entry.id)
    }
    const backend=chain.find(x=>x.id==='xbt-backend-identity').spec
    await backend.exec.fn()
    assert.deepEqual(rpcCalls.map(x=>x.method), ['getblockchaininfo','getdeploymentinfo','getblockhash'])
    assert.equal(rpcCalls[2].args.at(-1), String(policy.activationHeight))
    const rejected = [
      ['ordinary BTC', r=>{delete r.getdeploymentinfo.blake2b}],
      ['nested-only metadata', r=>{r.getdeploymentinfo.deployments.blake2b=r.getdeploymentinfo.blake2b; delete r.getdeploymentinfo.blake2b}],
      ['inactive fork', r=>{r.getdeploymentinfo.blake2b.active=false}],
      ['wrong activation', r=>{r.getdeploymentinfo.blake2b.height++}],
      ['string activation', r=>{r.getdeploymentinfo.blake2b.height=String(policy.activationHeight)}],
      ['missing activation', r=>{delete r.getdeploymentinfo.blake2b.height}],
      ['null fork metadata', r=>{r.getdeploymentinfo.blake2b=null}],
      ['wrong checkpoint', r=>{r.getblockhash='00'.repeat(32)}],
      ['wrong chain', r=>{r.getblockchaininfo.chain='regtest'}],
      ['still syncing', r=>{r.getblockchaininfo.initialblockdownload=true}],
      ['pruned backend', r=>{r.getblockchaininfo.pruned=true}],
      ['pre-activation tip', r=>{r.getblockchaininfo.blocks=policy.activationHeight-1}],
      ['missing tip', r=>{delete r.getblockchaininfo.blocks}],
    ]
    for (const [name, change] of rejected) {
      rpcReplies=structuredClone(recorded); change(rpcReplies)
      await assert.rejects(()=>backend.exec.fn(), /XBT requires/, name)
      assert.deepEqual(flags, [])
    }
    rpcReplies=structuredClone(recorded)
    await backend.exec.fn()
    console.log('PASS: real Knots response through the actual startup hook; '+rejected.length+' invalid backend cases refused')
    connection.packageId='knots-blake2b'
    rpcReplies=structuredClone(recorded)
    rpcReplies.getblockchaininfo.pruned=true
    rpcReplies.getblockchaininfo.pruneheight=policy.activationHeight+1
    rpcReplies.getblock='00'.repeat(200)
    rpcCalls.length=0
    await backend.exec.fn()
    assert.deepEqual(rpcCalls.map(x=>x.method),['getblockchaininfo','getdeploymentinfo','getblockhash','getblockhash','getblock'])
    assert.equal(rpcCalls[3].args.at(-1),String(policy.activationHeight))
    assert.equal(rpcCalls[4].args.at(-1),'0')
    for (const bad of ['', 'not hex', '00', {}, null]) {
      rpcReplies.getblock=bad
      await assert.rejects(()=>backend.exec.fn())
      assert.deepEqual(flags,[])
    }
    for (const bad of [-1, null, '123', rpcReplies.getblockchaininfo.blocks+1]) {
      rpcReplies.getblockchaininfo.pruneheight=bad
      await assert.rejects(()=>backend.exec.fn(),/XBT requires/)
    }
    connection.packageId='bitcoind';rpcReplies=structuredClone(recorded)
    let touched=false
    await policy.verifyHistoricalBlock(good,async()=>{touched=true})
    assert.equal(touched,false)
    const calls=[]
    await policy.verifyHistoricalBlock({pruned:true,pruneheight:100},async(method,...args)=>{
      calls.push([method,...args]);return method==='getblockhash'?'aa'.repeat(32):'00'.repeat(200)
    })
    assert.equal(calls[0][1],'99')
    await assert.rejects(()=>policy.verifyHistoricalBlock({pruned:true,pruneheight:100},async()=> 'invalid hash'))
    await assert.rejects(()=>policy.verifyHistoricalBlock({pruned:true,pruneheight:100},async()=>{throw Error('peer unavailable')}))
    console.log('PASS: pruned companion requires historical block availability; malformed/pruned fallback backends refuse before flag consumption')

    assert.deepEqual(chain.find(x=>x.id==='lightningd').spec.requires,['xbt-backend-identity'])
    assert.ok(chain.find(x=>x.id==='cln-application').spec.requires.includes('consume-flags'))
    assert.deepEqual(chain.find(x=>x.id==='lightningd').spec.exec.command.slice(0,7), ['/usr/local/libexec/swap-node/package_node.py','--mainnet','--profile','xbt-privkeyio-v1','--root','/root/.lightning','launch'])
    assert.deepEqual(flags,[]) // Merely reading startup flags never consumes them.
    const emergency = chain.find(x=>x.id==='emergency-recover').spec()
    assert.deepEqual((await emergency.exec.fn()).command, recovery.recoveryCommands('/root/.lightning').emergency)
    assert.deepEqual(chain.find(x=>x.id==='address-pregen').spec().exec.command,
      recovery.recoveryCommands('/root/.lightning').addresses)
    assert.deepEqual(flags,[]) // Planning recovery commands must not consume flags either.
    const { VersionGraph } = require('@start9labs/start-sdk')
    const { ExtendedVersion } = Module.createRequire(require.resolve('@start9labs/start-sdk'))('@start9labs/start-core/exver')
    const current = load('startos/versions/current.ts', {'../sdk':{sdk},'../xbtPolicy':policy}).current
    const v2 = load('startos/versions/v2.ts', {'../sdk':{sdk},'../xbtPolicy':policy}).v2
    const v3 = load('startos/versions/v3.ts', {'../sdk':{sdk},'../xbtPolicy':policy}).v3
    const graph = load('startos/versions/index.ts', {'./current':{current},'./v2':{v2},'./v3':{v3}}).versionGraph
    const from = ExtendedVersion.parse('#privkeyio:26.6.9:1')
    const to = ExtendedVersion.parse('#privkeyio:26.6.9:9')
    const fromV2 = ExtendedVersion.parse('#privkeyio:26.6.9:2')
    assert.ok(graph.canMigrateFrom().satisfiedBy(fromV2))
    assert.ok(graph.canMigrateFrom().satisfiedBy(from))
    for (const version of ['26.6.9:0','#privkeyio:26.6.8:0','#privkeyio:26.6.9:0','#legacy:26.6.9:0']) {
      assert.equal(graph.canMigrateFrom().satisfiedBy(ExtendedVersion.parse(version)),false)
    }
    assert.equal(graph.canMigrateTo().satisfiedBy(from),false)
    const savedVersions=[]
    const migrationEffects={setDataVersion:async({version})=>savedVersions.push(version)}
    const identityBefore=await fs.readFile(path.join(root,policy.marker),'utf8')
    await fs.mkdir(path.join(root,'bitcoin/swap-coordinator-v1'))
    await fs.writeFile(path.join(root,'bitcoin/swap-coordinator-v1/sentinel'),'existing-journal')
    await graph.migrate({effects:migrationEffects,from,to})
    await graph.migrate({effects:migrationEffects,from:fromV2,to})
    assert.equal(await fs.readFile(path.join(root,'bitcoin/swap-coordinator-v1/sentinel'),'utf8'),'existing-journal')
    assert.equal(await fs.readFile(path.join(root,policy.marker),'utf8'),identityBefore)
    assert.equal(savedVersions.at(-1),to.toString())
    await fs.mkdir(path.join(root,policy.swapDirs[0]))
    await assert.rejects(()=>graph.migrate({effects:migrationEffects,from,to}))
    await assert.rejects(()=>graph.migrate({effects:migrationEffects,from:fromV2,to}))
    await fs.rmdir(path.join(root,policy.swapDirs[0]))
    assert.deepEqual(flags,[])
    console.log('PASS: SDK migration accepts only the prior candidate, preserves identity/flags and refuses swap state')
    let publicationCleared=0
    const b=load('startos/backups.ts',{...mocks,'./live/localController':{clearPublication:async()=>{publicationCleared++}}})
    await b.createBackup()
    await backup.before()
    for (const name of ['bitcoin/swap-coordinator-v1','bitcoin/.swap-setup-*','bitcoin/lightningd.sqlite3','bitcoin/lightningd.sqlite3-wal','bitcoin/lightningd.sqlite3-shm','.commando-env']) assert.ok(backup.options.exclude.includes(name))
    await fs.writeFile(path.join(root,'bitcoin/emergency.recover'),'recovery-copy')
    await fs.writeFile(path.join(root,'.commando-env'),'discarded-credential')
    await fs.writeFile(path.join(root,'local-controller-enabled.json'),'{}')
    await backup.after({})
    assert.equal(publicationCleared,1)
    assert.equal(await policy.exists(path.join(root,'local-controller-enabled.json')),false)
    assert.equal(await policy.exists(path.join(root,'.commando-env')),false)
    assert.deepEqual(flags,[{restore:true}]);assert.equal(tasks.length,1)
    assert.equal(JSON.parse(await fs.readFile(path.join(root,'node-restored.json'),'utf8')).recovery,true)
    const saved=(await fs.readdir(path.join(root,'bitcoin'))).find(x=>x.startsWith('emergency.recover.restored-'))
    assert.equal(await fs.readFile(path.join(root,'bitcoin',saved),'utf8'),'recovery-copy')
    await chain.find(x=>x.id==='consume-flags').spec().exec.fn()
    assert.deepEqual(flags, [{restore:true}, {rescan:undefined,restore:undefined}])
    await fs.mkdir(path.join(root,policy.swapDirs[0]))
    await assert.rejects(()=>backup.before())
    await assert.rejects(()=>backup.after({}))
    console.log('PASS: backend/profile boundaries, foreign-wallet and symlink refusal, startup ordering, preserved flags, backup exclusions and restore hooks')
  } finally {await fs.rm(temp,{recursive:true,force:true})}
}
main().catch(e=>{console.error(e);process.exitCode=1})
