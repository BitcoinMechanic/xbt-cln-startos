import { copyFile, unlink, writeFile } from 'fs/promises'
import { constants } from 'fs'
import { join } from 'path'
import { verifyVolume, requireInactiveSwaps, exists } from './xbtPolicy'

// Shared with the funded recovery fixture. Never back up a resumable channel DB.
export const backupExcludes = [
  'bitcoin/lightning-rpc', 'bitcoin/lightningd.sqlite3',
  'bitcoin/lightningd.sqlite3-wal', 'bitcoin/lightningd.sqlite3-shm',
  'bitcoin/gossip_store', '.commando-env',
  'data/app/application-cln.log', 'bitcoin/*.log',
]

export async function prepareBackup(root: string) {
  await verifyVolume(root)
  await requireInactiveSwaps(root)
}

export async function prepareRestore(root: string) {
  await prepareBackup(root)
  await writeFile(join(root, 'node-restored.json'),
    JSON.stringify({ schema: 1, recovery: true }), { mode: 0o600 })
  const scb = join(root, 'bitcoin/emergency.recover')
  if (await exists(scb)) {
    await copyFile(scb, scb + '.restored-' + Date.now(), constants.COPYFILE_EXCL)
  }
  await unlink(join(root, '.commando-env')).catch((error: NodeJS.ErrnoException) => {
    if (error.code !== 'ENOENT') throw error
  })
}

export function recoveryCommands(rootDir: string): { emergency: [string, ...string[]], addresses: [string, ...string[]] } {
  return {
    emergency: ['lightning-cli', `--lightning-dir=${rootDir}`, 'emergencyrecover'],
    // Persist the same 10,000-address window before the operator's rescan.
    // This remains a bounded window, not recovery of arbitrarily high indexes.
    addresses: ['sh', '-c',
      `i=0; while [ $i -lt 10000 ]; do lightning-cli --lightning-dir=${rootDir} newaddr all > /dev/null || exit 1; i=$((i+1)); done`],
  }
}
