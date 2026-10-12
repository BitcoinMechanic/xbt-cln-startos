// Test adapter only. Production startup has no regtest bypass.
import { resolve } from 'path'
import { backupExcludes, prepareBackup, prepareRestore, recoveryCommands } from '../startos/recovery'

async function main() {
  const [mode, volume, runtime] = process.argv.slice(2)
  if (!['before', 'after'].includes(mode) || !volume || !runtime ||
      ![volume, runtime].every(p => resolve(p).startsWith('/results/'))) {
    throw new Error('Disposable /results paths and before/after mode required')
  }
  if (mode === 'before') await prepareBackup(volume)
  else await prepareRestore(volume)
  console.log(JSON.stringify({ excludes: backupExcludes, commands: recoveryCommands(runtime) }))
}
main().catch(e => { console.error(e); process.exitCode = 1 })
