import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { requireInactiveSwaps, verifyVolume } from '../xbtPolicy'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:3',
  releaseNotes: { en_US: 'Restore the bundled native gRPC plugin and explicitly load gRPC and CLNrest as required by the node configuration. Preserve the existing wallet, channels, UI and swap journals during a normal update.' },
  migrations: {
    up: IMPOSSIBLE,
    down: IMPOSSIBLE,
    other: {
      '=#privkeyio:26.6.9:2': {
        up: async () => {
          const root = sdk.volumes.main.subpath('')
          await verifyVolume(root)
          await requireInactiveSwaps(root)
        },
      },
    },
  },
})
