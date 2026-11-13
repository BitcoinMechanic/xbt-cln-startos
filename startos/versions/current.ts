import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:19',
  releaseNotes: { en_US: 'Add private editable channel labels in Payment Channels. Labels are stored in the node wallet datastore, survive restarts, and can be cleared to restore the peer alias.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:18': { up: async () => {} }, '=#privkeyio:26.6.9:17': { up: async () => {} }, '=#privkeyio:26.6.9:16': { up: async () => {} }, '=#privkeyio:26.6.9:15': { up: async () => {} }, '=#privkeyio:26.6.9:14': { up: async () => {} }, '=#privkeyio:26.6.9:13': { up: async () => {} }, '=#privkeyio:26.6.9:12': { up: async () => {} }, '=#privkeyio:26.6.9:11': { up: async () => {} }, '=#privkeyio:26.6.9:10': { up: async () => {} }, '=#privkeyio:26.6.9:9': { up: async () => {} }, '=#privkeyio:26.6.9:8': { up: async () => {} }, '=#privkeyio:26.6.9:7': { up: async () => {} }, '=#privkeyio:26.6.9:6': { up: async () => {} }, '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
