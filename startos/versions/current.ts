import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:5',
  releaseNotes: {
    en_US:
      'Adds a stopped-service finish action restricted to explicitly confirmed never-funded wallets. Preserves wallet data and recovery records, validates fresh monitoring and an empty database, and permits subsequent bounded backups',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
