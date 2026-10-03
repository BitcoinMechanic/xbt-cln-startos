import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'

export const current = VersionInfo.of({
  version: '0.1.0:0',
  releaseNotes: {
    en_US:
      'Experimental XBT fresh-wallet observation package. Pins CLN 81ba4099a63e, checks the Knots activation checkpoint before starting, and exposes an XBT peer interface and read-only node information. Do not fund or migrate wallets yet. Restored backups are blocked from starting until recovery support is implemented.',
  },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
