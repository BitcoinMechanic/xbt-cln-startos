import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:0',
  releaseNotes: { en_US: 'Fresh-wallet XBT node candidate with patched engine and CLN Application 26.09. Existing experimental XBT wallets/channels cannot be migrated by this release. Swap activation remains unavailable.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE },
})
