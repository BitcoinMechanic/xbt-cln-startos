import { IMPOSSIBLE, VersionInfo } from '@start9labs/start-sdk'
import { sdk } from '../sdk'
import { requireInactiveSwaps, verifyVolume } from '../xbtPolicy'
export const v2 = VersionInfo.of({
  version: '#privkeyio:26.6.9:2',
  releaseNotes: { en_US: 'Add explicitly enabled, bounded BTC/XBT swap coordinator actions and static recovery plugins. Preserve this privkeyio wallet, identity and channels on an ordinary update. Experimental XBT wallet import remains unsupported.' },
  migrations: {
    up: IMPOSSIBLE,
    down: IMPOSSIBLE,
    other: {
      '=#privkeyio:26.6.9:1': {
        up: async () => {
          const root = sdk.volumes.main.subpath('')
          await verifyVolume(root)
          await requireInactiveSwaps(root)
        },
      },
    },
  },
})
