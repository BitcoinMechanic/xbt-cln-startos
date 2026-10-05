import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_13 = VersionInfo.of({
  version: '0.1.0:13',
  releaseNotes: {
    en_US:
      'Adds dedicated read-only controller credential creation, inspection and revocation. No new listener or live swap activation.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
