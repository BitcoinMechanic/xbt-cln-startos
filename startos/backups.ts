import { copyFile, unlink, writeFile } from 'fs/promises'
import { constants } from 'fs'
import { rescanBlockchain } from './actions/rescanBlockchain'
import { storeJson } from './fileModels/store.json'
import { sdk } from './sdk'
import { verifyVolume, requireInactiveSwaps, exists } from './xbtPolicy'

export const { createBackup, restoreInit } = sdk.setupBackups(async () =>
  sdk.Backups.ofVolumes('main')
    .setOptions({ exclude: [
      'bitcoin/lightning-rpc', 'bitcoin/lightningd.sqlite3',
      'bitcoin/lightningd.sqlite3-wal', 'bitcoin/lightningd.sqlite3-shm',
      'bitcoin/gossip_store', '.commando-env',
      'data/app/application-cln.log', 'bitcoin/*.log',
    ] })
    .setPreBackup(async () => {
      const root = sdk.volumes.main.subpath('')
      await verifyVolume(root)
      await requireInactiveSwaps(root)
    })
    .setPostRestore(async effects => {
      const root = sdk.volumes.main.subpath('')
      await verifyVolume(root)
      await requireInactiveSwaps(root)
      // Persist a recovery marker before node startup. Never copy a stale DB.
      await writeFile(sdk.volumes.main.subpath('node-restored.json'),
        JSON.stringify({ schema: 1, recovery: true }), { mode: 0o600 })
      const scb = sdk.volumes.main.subpath('bitcoin/emergency.recover')
      if (await exists(scb)) {
        await copyFile(scb, scb + '.restored-' + Date.now(), constants.COPYFILE_EXCL)
      }
      await unlink(sdk.volumes.main.subpath('.commando-env')).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== 'ENOENT') throw error
      })
      await storeJson.merge(effects, { restore: true })
      await sdk.action.createOwnTask(effects, rescanBlockchain, 'important', {
        reason: 'Restore recovers keys and channel recovery data, not a resumable channel database. Rescan the XBT chain, recover and drain funds before starting fresh.',
      })
    }),
)
