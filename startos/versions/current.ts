import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:8',
  releaseNotes: { en_US: 'Trust a local Swap Controller once: create and renew scoped incoming and outgoing grants automatically. Preserve swap recovery, pause managed grants when trust is disabled, and never restore spending permission from backups.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:7': { up: async () => {} }, '=#privkeyio:26.6.9:6': { up: async () => {} }, '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
