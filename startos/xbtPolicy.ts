import { lstat, readFile, writeFile } from 'fs/promises'
import { join } from 'path'

export const activationHeight = 961640
export const activationHash = '0000000000000050c1e5f69672f459293be14f46e5a494e7a8c8541396f18eeb'
export const identity = { schema: 1, profile: 'xbt-privkeyio-v1', layout: 'bitcoin' }
export const marker = 'xbt-package-identity.json'
export const swapDirs = ['bounded-authority-v1', 'remote-authority-v1', 'customer-remote-v1', 'customer-invoices-v1', 'swap-gate-v1']

export function verifyBackend(chain: any, deployments: any, checkpoint: unknown) {
  if (chain?.chain !== 'main' || chain.initialblockdownload !== false ||
      chain.pruned !== false || !Number.isSafeInteger(chain.blocks) || chain.blocks < activationHeight ||
      deployments?.blake2b?.active !== true || deployments.blake2b.height !== activationHeight ||
      checkpoint !== activationHash) {
    throw new Error('XBT requires synced, unpruned BLAKE2b Knots with the pinned activation checkpoint')
  }
}

export function verifyNode(info: any) {
  if (info?.network !== 'bitcoin' || !/^0[23][0-9a-f]{64}$/.test(info?.id ?? '') ||
      !Number.isSafeInteger(info.blockheight) || info.blockheight < 0) throw new Error('Unexpected XBT node identity')
  for (const place of ['init', 'node', 'invoice']) {
    const value = info?.our_features?.[place]
    if (typeof value !== 'string' || value.length > 16384 || !/^(?:[0-9a-fA-F]{2})+$/.test(value)) throw new Error('Missing XBT feature identity')
    const bits = BigInt('0x' + value)
    if (!(bits & (1n << 512n)) || (bits & (1n << 513n))) throw new Error('Wrong XBT feature identity')
    if (place !== 'invoice' && (!(bits & (1n << 515n)) || (bits & (1n << 514n)))) throw new Error('Missing unified signing capability')
    if (place === 'invoice' && (bits & (3n << 514n))) throw new Error('Wrong XBT invoice features')
  }
}

export async function exists(path: string) {
  try { await lstat(path); return true } catch (e) {
    if ((e as NodeJS.ErrnoException).code === 'ENOENT') return false
    throw e
  }
}

export async function verifyVolume(root: string, fresh = false) {
  for (const name of ['xbt', 'xbt-regtest', 'regtest', 'testnet', 'signet', 'restore-blocked']) {
    if (await exists(join(root, name))) throw new Error('Existing or foreign Lightning state requires a separate migration')
  }
  const file = join(root, marker)
  if (!await exists(file)) {
    if (!fresh || await exists(join(root, 'bitcoin')) || await exists(join(root, 'hsm_secret'))) throw new Error('Unrecognized wallet layout; import is not supported')
    await writeFile(file, JSON.stringify(identity), { flag: 'wx', mode: 0o600 })
  }
  const stat = await lstat(file)
  if (!stat.isFile() || stat.isSymbolicLink() || stat.size > 1024) throw new Error('Invalid XBT package identity')
  const saved = JSON.parse(await readFile(file, 'utf8'))
  if (JSON.stringify(saved) !== JSON.stringify(identity)) throw new Error('XBT package identity changed')
  if (await exists(join(root, 'bitcoin')) && !(await lstat(join(root, 'bitcoin'))).isDirectory()) throw new Error('Invalid wallet directory')
}

export async function requireInactiveSwaps(root: string) {
  // No active coordinator adapter is registered by this node-only candidate.
  // Unknown authority must never be silently omitted and later re-created.
  for (const base of [root, join(root, 'bitcoin')]) {
    for (const name of swapDirs) if (await exists(join(base, name))) throw new Error('Swap state requires coordinator-aware backup and restore')
  }
}
