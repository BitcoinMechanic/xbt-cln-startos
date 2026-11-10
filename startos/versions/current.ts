import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:15',
  releaseNotes: { en_US: 'Renew idle automatic grants after channel changes without reactivating completed historical channels; expose expired-grant admission failures.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:14': { up: async () => {} }, '=#privkeyio:26.6.9:13': { up: async () => {} }, '=#privkeyio:26.6.9:12': { up: async () => {} }, '=#privkeyio:26.6.9:11': { up: async () => {} }, '=#privkeyio:26.6.9:10': { up: async () => {} }, '=#privkeyio:26.6.9:9': { up: async () => {} }, '=#privkeyio:26.6.9:8': { up: async () => {} }, '=#privkeyio:26.6.9:7': { up: async () => {} }, '=#privkeyio:26.6.9:6': { up: async () => {} }, '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
