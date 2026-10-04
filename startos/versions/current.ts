import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:11',
  releaseNotes: {
    en_US:
      'Allows sequential private channel attempts after verified cooperative-close archival; preserves historical funding records and blocks stale funding requests',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
