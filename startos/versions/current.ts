import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:18',
  releaseNotes: {
    en_US: 'Include Core Lightning 26.06.9 security fixes and correct CLBOSS Auto Close configuration. Retain explicit forward pilot authority and existing node identities.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
