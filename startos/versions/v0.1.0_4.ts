import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_4 = VersionInfo.of({
  version: '0.1.0:4',
  releaseNotes: {
    en_US:
      'Fixes recovery-worker registration: retain the daemon chain returned by the immutable SDK builder. Existing restore intents now launch the worker and recovery health check. Adds a wrapper topology regression test.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
