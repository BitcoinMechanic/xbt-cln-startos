import { writeFile, rename } from 'fs/promises'
import { sdk } from '../sdk'
import { peerHostId, peerInterfaceId } from '../interfaces'

// UI-only metadata. LAN bindings must never be added to public gossip, and
// updating this file must not restart the Lightning daemon.
export const peerUiAddresses = sdk.setupOnInit(async (effects) => {
  const addresses = await sdk.host.getOwn(effects, peerHostId, host => {
    const iface = host && Object.values(host.bindings)
      .flatMap(binding => Object.values(binding.interfaces))
      .find(iface => iface.id === peerInterfaceId)
    return iface ? iface.addressInfo.nonLocal.filter({ exclude: { kind: 'bridge' } }).format() : []
  }).const()
  const path = sdk.volumes.main.subpath('peer-ui-addresses.json')
  await writeFile(path + '.tmp', JSON.stringify(addresses), { mode: 0o644 })
  await rename(path + '.tmp', path)
})
