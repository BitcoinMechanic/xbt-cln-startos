import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:15',
  releaseNotes: {
    en_US:
      'Adds explicit bounded XBT gate activation, durable gate journal, restore invalidation and a separate read-only gate credential. Controller live execution remains disabled.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
