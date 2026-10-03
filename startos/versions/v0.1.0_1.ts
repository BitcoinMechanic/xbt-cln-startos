import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_1 = VersionInfo.of({
  version: '0.1.0:1',
  releaseNotes: {
    en_US:
      'Adds stopped-service backup and fresh-volume restore for empty XBT observation wallets. Restored identity is checked against the backup. Wallets with recorded activity and older backups without a receipt remain blocked. Do not fund or migrate wallets yet.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
