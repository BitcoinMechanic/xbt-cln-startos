import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:6',
  releaseNotes: { en_US: 'Prefer local knots-blake2b for RPC and credentials; use bitcoind only when knots-blake2b is not installed. Preserve chain identity and unpruned-backend checks.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
