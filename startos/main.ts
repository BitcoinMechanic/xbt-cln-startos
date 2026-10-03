import { FileHelper } from '@start9labs/start-sdk'
import { manifest as bitcoinManifest } from 'bitcoin-core-startos/startos/manifest'
import { lstat } from 'fs/promises'
import { sdk } from './sdk'
import {
  bitcoinDataDir,
  bitcoindRpcBridge,
  mainMounts,
  rootDir,
  peerPort,
} from './utils'
import { activationHeight, verifyBackend, nodeHealth } from './xbt-policy'

export const main = sdk.setupMain(async ({ effects }) => {
  // A distinct package volume is mandatory. Never silently import a BTC wallet
  // or resume a restored stale channel database.
  for (const name of ['bitcoin', 'restore-blocked']) {
    try {
      await lstat(sdk.volumes.main.subpath(name))
    } catch (error: any) {
      if (error.code === 'ENOENT') continue
      throw error
    }
    throw new Error(
      'Wallet import or restored backup detected; this observation build cannot start it',
    )
  }
  const backend = await bitcoindRpcBridge(effects)
  if (!backend) throw new Error('Knots RPC bridge is not available')
  const sub = sdk.SubContainer.of(
    effects,
    { imageId: 'lightning' },
    mainMounts.mountDependency<typeof bitcoinManifest>({
      dependencyId: 'bitcoind',
      mountpoint: bitcoinDataDir,
      subpath: null,
      readonly: true,
      volumeId: 'main',
    }),
    'lightning-sub',
  )

  // Follow cookie replacement, but do not shut CLN down just because the
  // backend temporarily removes its cookie while restarting.
  await FileHelper.string(`${await sub.rootfs}${bitcoinDataDir}/.cookie`)
    .read(
      (c) => c,
      (prev, next) => next === null || prev === next,
    )
    .const(effects)

  const cli = [
    'lightning-cli',
    `--lightning-dir=${rootDir}`,
    '--network=xbt',
    '--json',
  ]
  const backendCli = [
    'bitcoin-cli',
    `-rpcconnect=${backend.host}`,
    `-rpcport=${backend.port}`,
    `-rpccookiefile=${bitcoinDataDir}/.cookie`,
    '-rpcclienttimeout=30',
  ]
  const rpc = async (method: string, ...args: string[]) => {
    const res = await sub.exec([...backendCli, method, ...args])
    if (res.exitCode !== 0)
      throw new Error(
        'Knots identity RPC unavailable; private details withheld',
      )
    return String(res.stdout).trim()
  }
  return sdk.Daemons.of(effects)
    .addOneshot('xbt-backend-identity', {
      subcontainer: sub,
      exec: {
        fn: async () => {
          const chain = JSON.parse(await rpc('getblockchaininfo'))
          const deployments = JSON.parse(await rpc('getdeploymentinfo'))
          const checkpoint = await rpc('getblockhash', String(activationHeight))
          verifyBackend(chain, deployments, checkpoint)
          return null
        },
      },
      requires: [],
    })
    .addDaemon('lightningd', {
      subcontainer: sub,
      exec: {
        command: [
          'lightningd',
          `--lightning-dir=${rootDir}`,
          '--conf=/dev/null',
          '--network=xbt',
          '--database-upgrade=true',
          `--bitcoin-rpcconnect=${backend.host}`,
          `--bitcoin-rpcport=${backend.port}`,
          `--bitcoin-datadir=${bitcoinDataDir}`,
          `--bind-addr=0.0.0.0:${peerPort}`,
          '--autolisten=false',
          '--announce-addr-discovered=false',
        ],
      },
      ready: {
        display: 'XBT Node',
        fn: async () => {
          const res = await sub.exec([...cli, 'getinfo'])
          if (res.exitCode !== 0)
            return {
              result: 'loading',
              message: 'Waiting for XBT RPC',
            }
          try {
            return nodeHealth(JSON.parse(String(res.stdout)))
          } catch {
            return { result: 'failure', message: 'Invalid XBT RPC response' }
          }
        },
      },
      requires: ['xbt-backend-identity'],
    })
})
