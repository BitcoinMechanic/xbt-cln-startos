import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:6',
  releaseNotes: {
    en_US:
      'Adds bounded on-chain pilot actions: deposit address, confirmed funds, withdrawal preparation, explicit review and submission, cancellation and status. No automatic transaction retry; maximum pilot wallet balance is 100,000 sats',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
