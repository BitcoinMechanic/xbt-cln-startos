import { T } from '@start9labs/start-sdk'
import { rpcHostId, rpcPort } from 'bitcoin-core-startos/startos/utils'
import { sdk } from './sdk'

// Published backend contract, checked against paulscode/knots-blake2b-startos
// 3847fce974be7d944f37f97e47b3851444c9ffc5/startos/{utils,main}.ts.
// Keep this small contract local: that package uses a different SDK generation.
export const backends = {
  'knots-blake2b': { hostId: 'rpc', internalPort: 18443, healthChecks: ['node', 'chain'] },
  bitcoind: { hostId: rpcHostId, internalPort: rpcPort, healthChecks: ['bitcoind', 'sync-progress'] },
} as const
export type BackendId = keyof typeof backends
export async function selectedBackend(effects: T.Effects): Promise<BackendId> {
  // Watch installation presence only. A stopped/unhealthy preferred backend
  // must never make us silently switch to the other chain's service.
  const installed = await sdk.getServiceManifest(effects, 'knots-blake2b', m => m !== null).const()
  return installed ? 'knots-blake2b' : 'bitcoind'
}
export async function backendRpcBridge(effects: T.Effects) {
  const packageId = await selectedBackend(effects)
  const { hostId, internalPort } = backends[packageId]
  const addr = await sdk.host.getBridgeAddress(effects, { packageId, hostId, internalPort, ssl: false }).const()
  if (!addr) return null
  const url = new URL('http://' + addr)
  return { packageId, host: url.hostname.replace(/^\[|\]$/g, ''), port: Number(url.port || 80) }
}
