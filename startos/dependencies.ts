import { sdk } from './sdk'

export const setDependencies = sdk.setupDependencies(async () => ({
  bitcoind: {
    healthChecks: ['bitcoind', 'sync-progress'],
    kind: 'running',
    // Package IDs and version ranges cannot distinguish BTC from XBT.
    // Startup verifies the chain through RPC before lightningd creates a wallet.
    versionRange: '*',
  },
}))
