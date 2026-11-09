import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:12',
  releaseNotes: { en_US: 'Support routes up to 576 blocks and safely refresh idle automatically managed outgoing grants. Preserve the additional 150-block incoming recovery margin, existing swap authority, manual grants, fee limits and hop limits.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:11': { up: async () => {} }, '=#privkeyio:26.6.9:10': { up: async () => {} }, '=#privkeyio:26.6.9:9': { up: async () => {} }, '=#privkeyio:26.6.9:8': { up: async () => {} }, '=#privkeyio:26.6.9:7': { up: async () => {} }, '=#privkeyio:26.6.9:6': { up: async () => {} }, '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
