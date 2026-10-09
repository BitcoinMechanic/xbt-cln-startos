import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
export const current = VersionInfo.of({
  version: '0.1.0:21',
  releaseNotes: { en_US: 'Grant renewal verifies completed swap history after channels close, preserving original funding and HTLC bindings. Clearer receiving-channel diagnostics; existing records and recovery authority retained.' },
  migrations: { up: async () => {}, down: IMPOSSIBLE },
})
