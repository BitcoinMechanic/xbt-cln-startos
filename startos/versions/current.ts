import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:11',
  releaseNotes: { en_US: 'Support recipient invoice timelocks within the existing 288-block route budget. Bind final payment checks to the saved route and preserve recovery margins. Report safe invoice and route failures explicitly.' },
  migrations: { up: IMPOSSIBLE, down: IMPOSSIBLE, other: { '=#privkeyio:26.6.9:10': { up: async () => {} }, '=#privkeyio:26.6.9:9': { up: async () => {} }, '=#privkeyio:26.6.9:8': { up: async () => {} }, '=#privkeyio:26.6.9:7': { up: async () => {} }, '=#privkeyio:26.6.9:6': { up: async () => {} }, '=#privkeyio:26.6.9:5': { up: async () => {} }, '=#privkeyio:26.6.9:3': { up: async () => {} }, '=#privkeyio:26.6.9:4': { up: async () => {} } } },
})
