import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_8 = VersionInfo.of({
  version: '0.1.0:8',
  releaseNotes: {
    en_US:
      'Generates a fresh XBT deposit address for every request. Earlier addresses and wallet records remain intact; backup limits are unchanged',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
