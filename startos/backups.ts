import { sdk } from './sdk'
import { mainMounts, rootDir } from './utils'
import { T } from '@start9labs/start-sdk'

async function check(effects: T.Effects, mode: 'capture' | 'restore') {
  await sdk.SubContainer.withTemp(
    effects,
    { imageId: 'lightning' },
    mainMounts,
    `empty-backup-${mode}`,
    async (sub) => {
      const result = await sub.exec([
        '/opt/xbt-venv/bin/python',
        '/usr/local/libexec/xbt-empty-backup.py',
        mode,
        rootDir,
      ])
      if (result.exitCode !== 0)
        throw new Error(
          'Empty-wallet backup/restore refused. Wallet must have no recorded activity; restore requires a fresh volume. Keep the original wallet and backup.',
        )
    },
  )
}

// StartOS stops the service for the complete backup operation. Inspect the
// quiescent database, but never include it in a restorable Lightning backup.
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
    .setPreBackup(async (effects) => check(effects, 'capture'))
    .setPostRestore(async (effects) => check(effects, 'restore')),
)
