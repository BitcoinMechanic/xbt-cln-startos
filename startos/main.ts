import { FileHelper } from '@start9labs/start-sdk'
import { manifest as bitcoinManifest } from 'bitcoin-core-startos/startos/manifest'
import { lstat, readFile } from 'fs/promises'
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
  let restoredIdentity: string | undefined
  try {
    const receipt = JSON.parse(
      await readFile(
        sdk.volumes.main.subpath('restored-identity.json'),
        'utf8',
      ),
    )
    if (receipt.schema !== 1 || !/^0[23][0-9a-f]{64}$/.test(receipt.node_id))
      throw new Error('Invalid restored identity record')
    restoredIdentity = receipt.node_id
  } catch (error: any) {
    if (error.code !== 'ENOENT') throw error
  }
  let recovery: { phase: string; scan_start?: number; channels?: string[]; node_id?: string; completion_scope?: string } | undefined
  try {
    recovery = JSON.parse(await readFile(
      sdk.volumes.main.subpath('recovery-intent.json'), 'utf8',
    ))
    if (!recovery || !['prepared', 'importing', 'imported', 'finished-empty'].includes(recovery.phase))
      throw new Error('Invalid recovery intent')
    if (recovery.scan_start !== undefined && (!Number.isSafeInteger(recovery.scan_start) || recovery.scan_start < 1 || recovery.scan_start > 2147483647))
      throw new Error('Invalid recovery scan starting height')
    if (recovery.phase === 'finished-empty') {
      if (!restoredIdentity || recovery.node_id !== restoredIdentity ||
          !Array.isArray(recovery.channels) || recovery.channels.length !== 0 ||
          recovery.completion_scope !== 'operator-confirmed-never-funded')
        throw new Error('Invalid empty-wallet completion record')
      recovery = undefined // Keep the audit record; no further rescan or worker.
    }
  } catch (error: any) {
    if (error.code !== 'ENOENT') throw error
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
  const daemons = sdk.Daemons.of(effects)
    .addOneshot('xbt-backend-identity', {
      subcontainer: sub,
      exec: {
        fn: async () => {
          const chain = JSON.parse(await rpc('getblockchaininfo'))
          const deployments = JSON.parse(await rpc('getdeploymentinfo'))
          const checkpoint = await rpc('getblockhash', String(activationHeight))
          verifyBackend(chain, deployments, checkpoint)
          if (recovery && (recovery.scan_start ?? 1) > chain.blocks)
            throw new Error('Recovery scan starting height exceeds the backend tip')
          const birth = await sub.exec([
            '/opt/xbt-venv/bin/python', '/usr/local/libexec/xbt-recovery.py',
            'record-birth', rootDir, String(chain.blocks),
          ])
          if (birth.exitCode !== 0) throw new Error('Wallet birth record check failed')
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
          ...(recovery && recovery.phase !== 'imported' ? [`--rescan=-${recovery.scan_start ?? 1}`] : []),
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
            const info = JSON.parse(String(res.stdout))
            if (restoredIdentity && info.id !== restoredIdentity)
              return {
                result: 'failure',
                message:
                  'Restored node identity does not match backup; keep this wallet unfunded',
              }
            const health = nodeHealth(info)
            if (health.result === 'loading' && recovery)
              return { ...health, message: `Recovery scan: block ${info.blockheight}; configured start ${recovery.scan_start ?? 1}. Waiting for sync.` }
            return health
          } catch {
            return { result: 'failure', message: 'Invalid XBT RPC response' }
          }
        },
      },
      requires: ['xbt-backend-identity'],
    })
  if (recovery) {
    return daemons.addDaemon('xbt-recovery', {
      subcontainer: sub,
      exec: { command: ['/opt/xbt-venv/bin/python', '/usr/local/libexec/xbt-recovery.py', 'run', rootDir] },
      requires: ['lightningd'],
      ready: {
        display: 'XBT Recovery',
        fn: async () => {
          try {
            const status = JSON.parse(await readFile(
              sdk.volumes.main.subpath('recovery-status.json'), 'utf8',
            ))
            if (!Number.isFinite(status.checked_at) || Date.now() / 1000 - status.checked_at > 90)
              return { result: 'loading', message: 'Waiting for fresh recovery status' }
            if (status.phase === 'attention')
              return { result: 'failure', message: 'Recovery needs inspection; retain the original backup' }
            return {
              result: 'loading',
              message: status.phase === 'monitoring'
                ? `Recovery active (scan start ${status.scan_start ?? 1}): ${status.waiting_for_close} awaiting peer close, ${status.onchain_channels} on-chain. Manual funds verification required.`
                : 'Recovery is scanning the chain or importing channel backups',
            }
          } catch {
            return { result: 'loading', message: 'Waiting for recovery status' }
          }
        },
      },
    })
  }
  return daemons
})
