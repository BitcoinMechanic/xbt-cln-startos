import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:9',
  releaseNotes: {
    en_US:
      'Allows bounded private-channel funding from larger wallets and reports local validation failures. Channel-size, fee-rate, input-count and no-resubmission guards remain in place',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
