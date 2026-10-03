import { writeFile } from 'fs/promises'
import { sdk } from './sdk'

// Do not restore an old Lightning commitment database as a live wallet.
// This observation release preserves keys/SCBs, but deliberately blocks startup
// after restoration; channel recovery must be implemented and tested first.
export const { createBackup, restoreInit } = sdk.setupBackups(async () =>
  sdk.Backups.ofVolumes('main')
    .setOptions({
      exclude: [
        'xbt/lightning-rpc',
        'xbt/lightningd.sqlite3',
        'xbt/lightningd.sqlite3-wal',
        'xbt/lightningd.sqlite3-shm',
        'xbt/gossip_store',
      ],
    })
    .setPostRestore(async () => {
      await writeFile(
        sdk.volumes.main.subpath('restore-blocked'),
        'XBT observation build: backup recovery is not enabled. Do not delete this marker.\n',
        { mode: 0o600 },
      )
    }),
)
