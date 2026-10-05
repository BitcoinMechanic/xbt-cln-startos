// Execute the wrapper factory with the REAL SDK's immutable daemon builder.
// Files and container operations are mocked; no daemon or wallet is started.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const { Daemons } = require(path.join(path.dirname(require.resolve('@start9labs/start-sdk')), 'mainFn/Daemons.js'))
const source = ts.transpileModule(fs.readFileSync('startos/main.ts', 'utf8'), {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
}).outputText
const id = '02' + '12'.repeat(32)

async function fixture(intent) {
  let healthStatus = { phase: 'monitoring', checked_at: Date.now() / 1000,
    waiting_for_close: 0, onchain_channels: 0, scan_start: 974000 }
  const missing = () => { throw Object.assign(new Error('missing fixture'), { code: 'ENOENT' }) }
  const sub = { rootfs: '/fixture', exec: async () => { throw new Error('unexpected container RPC') } }
  const sdk = {
    setupMain: fn => fn,
    volumes: { main: { subpath: name => name } },
    SubContainer: { of: () => sub }, Daemons,
  }
  const modules = {
    '@start9labs/start-sdk': { FileHelper: { string: () => ({ read: () => ({ const: async () => 'cookie' }) }) } },
    'bitcoin-core-startos/startos/manifest': { manifest: {} },
    'fs/promises': {
      lstat: async () => missing(),
      readFile: async name => {
        if (!intent) return missing()
        if (name === 'restored-identity.json') return JSON.stringify({ schema: 1, node_id: id })
        if (name === 'recovery-intent.json') return JSON.stringify(intent)
        if (name === 'recovery-status.json') return JSON.stringify(healthStatus)
        return missing()
      },
    },
    './sdk': { sdk },
    './utils': { bitcoinDataDir: '/mnt/bitcoin', rootDir: '/root/.lightning', peerPort: 9735, clnrestPort: 3010,
      bitcoindRpcBridge: async () => ({ host: 'fixture', port: 8332 }),
      mainMounts: { mountDependency: () => ({}) } },
    './xbt-policy': { activationHeight: 961640, verifyBackend: () => {}, nodeHealth: () => ({ result: 'success' }) },
  }
  const exports = {}
  vm.runInNewContext(source, { exports, require: name => {
    assert.ok(name in modules, `Unexpected import ${name}`)
    return modules[name]
  } })
  const built = await exports.main({ effects: {} })
  return { entries: built.entries, status: value => { healthStatus = value } }
}

async function run() {
  const fresh = await fixture(null)
  assert.deepEqual(fresh.entries.map(e => e.id), ['xbt-backend-identity', 'lightningd'])
  assert.ok(fresh.entries[1].exec.command.includes('--clnrest-port=3010'))
  assert.ok(fresh.entries[1].exec.command.includes('--clnrest-protocol=http'))
  assert.ok(fresh.entries[1].exec.command.includes('--clnrest-host=0.0.0.0'))
  for (const phase of ['prepared', 'importing', 'imported']) {
    const f = await fixture({ phase, scan_start: 974000 })
    assert.deepEqual(f.entries.map(e => e.id), ['xbt-backend-identity', 'lightningd', 'xbt-recovery'])
    const node = f.entries[1], recovery = f.entries[2]
    assert.equal(JSON.stringify(recovery.requires), JSON.stringify(['lightningd']))
    assert.ok(recovery.exec.command.includes('/usr/local/libexec/xbt-recovery.py'))
    assert.equal(node.exec.command.includes('--rescan=-974000'), phase !== 'imported')
    assert.equal((await recovery.ready.fn()).result, 'loading')
    f.status({ phase: 'attention', checked_at: Date.now() / 1000 })
    assert.equal((await recovery.ready.fn()).result, 'failure')
    f.status({ phase: 'monitoring', checked_at: 1 })
    assert.equal((await recovery.ready.fn()).result, 'loading')
  }
  const completed = { phase: 'finished-empty', channels: [], node_id: id, completion_scope: 'operator-confirmed-never-funded' }
  const finished = await fixture(completed)
  assert.equal(finished.entries.length, 2)
  assert.ok(!finished.entries[1].exec.command.some(x => x.startsWith('--rescan=')))
  await assert.rejects(() => fixture({ ...completed, node_id: 'wrong' }))
  await assert.rejects(() => fixture({ ...completed, channels: ['unexpected'] }))
  await assert.rejects(() => fixture({ ...completed, completion_scope: 'other' }))
  console.log('XBT recovery daemon registration and pending/error health checks OK')
}
run().catch(error => { console.error(error); process.exitCode = 1 })
