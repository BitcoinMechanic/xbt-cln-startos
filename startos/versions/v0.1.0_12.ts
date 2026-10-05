import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_12 = VersionInfo.of({
  version: '0.1.0:12',
  releaseNotes: {
    en_US:
      'Adds inert pinned swap modules and identity-bound coordinator preparation; live gates remain inactive',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
