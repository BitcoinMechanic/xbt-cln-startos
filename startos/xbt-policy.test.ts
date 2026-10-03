import assert from 'node:assert/strict'
import {
  activationHash,
  activationHeight,
  verifyBackend,
  nodeHealth,
} from './xbt-policy'

const chain = {
  chain: 'main',
  initialblockdownload: false,
  blocks: 975000,
  pruned: false,
}
const deployments = { blake2b: { active: true, height: activationHeight } }
verifyBackend(chain, deployments, activationHash)
for (const changed of [
  { ...chain, chain: 'regtest' },
  { ...chain, initialblockdownload: true },
  { ...chain, pruned: true },
  { ...chain, blocks: activationHeight - 1 },
  { ...chain, blocks: '975000' },
])
  assert.throws(() => verifyBackend(changed, deployments, activationHash))
for (const changed of [
  {},
  { blake2b: { active: false, height: activationHeight } },
  { blake2b: { active: true, height: 1 } },
]) {
  assert.throws(() => verifyBackend(chain, changed, activationHash))
}
assert.throws(() => verifyBackend(chain, deployments, '00'.repeat(32)))
assert.equal(nodeHealth({ network: 'bitcoin' }).result, 'failure')
assert.equal(
  nodeHealth({ network: 'xbt', warning_lightningd_sync: 'syncing' }).result,
  'loading',
)
assert.equal(nodeHealth({ network: 'xbt' }).result, 'success')
console.log('XBT backend and health policy checks OK')
