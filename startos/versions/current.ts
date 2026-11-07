import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:4',
  releaseNotes: { en_US: 'Retire unused outgoing swap authority without waiting for the recipient invoice to expire. Requires no send intent and fresh unused-payment/channel checks; permanently prevents later sending and preserves budgets, records, wallets and channels.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:3': { up: async () => {} } } },
})
