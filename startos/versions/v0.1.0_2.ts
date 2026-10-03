import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_2 = VersionInfo.of({
  version: '0.1.0:2',
  releaseNotes: {
    en_US:
      'Experimental bounded backup and force-close recovery integration. Fresh database only, settled normal channels, no pending HTLCs and address indices at most 50. Recovery remains pending until manual funds verification. Validate with the packaged regtest before live funding.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
