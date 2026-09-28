import { IMPOSSIBLE, T, VersionInfo } from '@start9labs/start-sdk'
import { clnConfig, dropClboss } from '../fileModels/config'

//CLBOSS is no longer shipped, so a config that loaded it names a binary that is not
//there and lightningd exits at startup. Every edge into this version runs this.
const removeClboss = async ({ effects }: { effects: T.Effects }) => {
  const form = await clnConfig.read().once()
  const plugins = (form?.raw?.plugin ?? []).filter(
    (p): p is string => typeof p === 'string',
  )
  await clnConfig.merge(effects, {
    raw: { ...(form?.raw ?? {}), ...dropClboss(plugins) },
  })
}

export const current = VersionInfo.of({
  version: '#blake:26.6.8:0',
  releaseNotes: {
    en_US: `Core Lightning v26.06.8-blake2b.5, based on upstream v26.06.8. It includes upstream's security fixes, and we strongly recommend updating.

## Notes for operators

- Every Lightning node you connect to must also update. The feature bits moved, so this version and the previous one will not connect to each other.
- Channels already open carry over: their stored channel type is updated when the database is upgraded.
- Downgrading to the previous version is not possible.
- Fund channels only from coins received past activation.

Your node's configuration does not change.`,
  },
  migrations: {
    up: removeClboss,
    //Refuse every downgrade. Channels opened here negotiate unified signing, and a build without it
    //computes a different signature hash, so it cannot close them. lightning-downgrade refuses for
    //the same reason.
    down: IMPOSSIBLE,
    other: {
      //Arriving from the unflavored build, or from the header-only flavor. Both are Core Lightning
      //v26.06.7; lightningd upgrades the wallet database on its first start.
      ['^26']: {
        up: removeClboss,
      },
      //Arriving from the first blake flavor, whose web interface used commando.
      ['#blake:26.6.7:1']: {
        up: removeClboss,
      },
      //Arriving from the flavor that shipped CLBOSS and linked to a SHA256d chain explorer.
      ['#blake:26.6.7:2']: {
        up: removeClboss,
      },
      //Arriving from Core Lightning v26.06.7-blake2b.4.
      ['#blake:26.6.7:3']: {
        up: removeClboss,
      },
    },
  },
})
