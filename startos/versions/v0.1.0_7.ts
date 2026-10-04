import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const v_0_1_0_7 = VersionInfo.of({
  version: '0.1.0:7',
  releaseNotes: {
    en_US:
      'Adds peer connection, single private-channel funding, status and cooperative close actions. Funding and close intent persist before RPC submission; repeated actions reconcile without resending. Channel pilot limited to 20,000–80,000 sats',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
