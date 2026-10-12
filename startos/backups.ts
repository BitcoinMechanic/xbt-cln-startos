import { rescanBlockchain } from './actions/rescanBlockchain'
import { storeJson } from './fileModels/store.json'
import { sdk } from './sdk'
import { backupExcludes, prepareBackup, prepareRestore } from './recovery'

export const { createBackup, restoreInit } = sdk.setupBackups(async () =>
  sdk.Backups.ofVolumes('main')
    .setOptions({ exclude: backupExcludes })
    .setPreBackup(async () => prepareBackup(sdk.volumes.main.subpath('')))
    .setPostRestore(async effects => {
      await prepareRestore(sdk.volumes.main.subpath(''))
      await storeJson.merge(effects, { restore: true })
      await sdk.action.createOwnTask(effects, rescanBlockchain, 'important', {
        reason: 'Restore recovers keys and channel recovery data, not a resumable channel database. Rescan the XBT chain, recover and drain funds before starting fresh.',
      })
    }),
)
