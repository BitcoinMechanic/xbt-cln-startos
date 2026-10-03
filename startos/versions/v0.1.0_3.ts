import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_3 = VersionInfo.of({
  version: '0.1.0:3',
  releaseNotes: {
    en_US:
      'Records a conservative scan starting point before creating new wallets. Adds a stopped-service action to shorten a known-never-funded pending restore without deleting data. Displays scan progress. Existing backups retain a full scan unless explicitly adjusted.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
