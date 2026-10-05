import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:14',
  releaseNotes: {
    en_US:
      'Adds rune-authenticated CLN REST behind StartOS edge HTTPS. Interface URLs contain no credentials; live swap gates remain disabled.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
