const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')
const sdkRoot = path.dirname(require.resolve('@start9labs/start-sdk/package.json'))
const { MultiHost } = require(require.resolve('@start9labs/start-core/interfaces/Host', { paths: [sdkRoot] }))
function load(file, modules) {
  const source = ts.transpileModule(fs.readFileSync(file, 'utf8'), {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 },
  }).outputText
  const exports = {}
  vm.runInNewContext(source, { exports, require: name => {
    assert.ok(name in modules, `Unexpected import ${name}`); return modules[name]
  } })
  return exports
}
async function run() {
  const binds = [], exports = []
  const effects = { bind: async b => binds.push(b), exportServiceInterface: async i => exports.push(i) }
  const sdk = { setupInterfaces: fn => fn,
    MultiHost: { of: (effects, id) => new MultiHost({ effects, id }) },
    createInterface: (effects, options) => ({ options: { ...options, effects } }),
  }
  const module = load('startos/interfaces.ts', { './sdk': { sdk }, './utils': { peerPort: 9735, clnrestPort: 3010 } })
  await module.setInterfaces({ effects })
  assert.equal(binds.length, 2)
  const binding = binds.find(b => b.id === 'controller-rpc')
  assert.equal(binding.internalPort, 3010)
  assert.equal(binding.secure, null)
  assert.equal(binding.addSsl.scheme, 'https')
  assert.equal(binding.addSsl.addXForwardedHeaders, false)
  const api = exports.find(i => i.id === 'controller-rpc')
  assert.equal(api.type, 'api'); assert.equal(api.masked, true)
  assert.equal(api.addressInfo.sslScheme, 'https')
  assert.equal(api.addressInfo.suffix, '')
  assert.equal(api.addressInfo.username, null)
  assert.equal(exports.find(i => i.id === 'peer').addressInfo.internalPort, 9735)
  console.log('XBT controller interface: real SDK edge TLS binding, credential-free URL OK')
}
run().catch(error => { console.error(error); process.exit(1) })
