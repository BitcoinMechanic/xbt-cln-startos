import { unlink, writeFile } from 'fs/promises'
import { sdk } from './sdk'
import { mainMounts, rootDir } from './utils'
import { T } from '@start9labs/start-sdk'

async function check(effects: T.Effects, mode: 'capture' | 'restore') {
  await sdk.SubContainer.withTemp(
    effects,
    { imageId: 'lightning' },
    mainMounts,
    `recovery-backup-${mode}`,
    async (sub) => {
      const result = await sub.exec([
        '/opt/xbt-venv/bin/python',
        '/usr/local/libexec/xbt-recovery.py',
        mode,
        rootDir,
      ])
      if (result.exitCode !== 0)
        throw new Error(
          'Bounded recovery backup/restore refused. Pending HTLCs, non-normal channels, reserved outputs, or address indices beyond 50 require separate recovery support. Keep the original wallet and backup.',
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
        'xbt-gate-activation.json',
        'xbt-gate.lock',
        'xbt/lightning-rpc',
        'xbt/lightningd.sqlite3',
        'xbt/lightningd.sqlite3-wal',
        'xbt/lightningd.sqlite3-shm',
        'xbt/gossip_store',
      ],
    })
    .setPreBackup(async (effects) => check(effects, 'capture'))
    .setPostRestore(async (effects) => {
      await writeFile(sdk.volumes.main.subpath('xbt-gate-restored.json'), JSON.stringify({ schema: 1, blocked: true }), { mode: 0o600 })
      await unlink(sdk.volumes.main.subpath('xbt-gate-activation.json')).catch((error: NodeJS.ErrnoException) => {
        if (error.code !== 'ENOENT') throw error
      })
      await check(effects, 'restore')
    }),
)
