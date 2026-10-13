import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { requireInactiveSwaps, verifyVolume } from '../xbtPolicy'
export const current = VersionInfo.of({
  version: '#privkeyio:26.6.9:1',
  releaseNotes: { en_US: 'Correct the Knots activation response parsing that blocked first startup. Node engine, UI and wallet format are unchanged. Updates only the previous privkeyio candidate; legacy wallet/channel import and swap activation remain unavailable.' },
  migrations: {
    up: IMPOSSIBLE,
    down: IMPOSSIBLE,
    other: {
      '=#privkeyio:26.6.9:0': {
        up: async () => {
          const root = sdk.volumes.main.subpath('')
          await verifyVolume(root)
          await requireInactiveSwaps(root)
        },
      },
    },
  },
})
