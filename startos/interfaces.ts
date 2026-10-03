import { sdk } from './sdk'
import { peerPort } from './utils'

export const peerHostId = 'peer'
export const peerInterfaceId = 'peer'
// Retained for the unregistered legacy action sources only.
export const watchtowerHostId = 'watchtower'
export const teosInterfaceId = 'watchtower'

export const setInterfaces = sdk.setupInterfaces(async ({ effects }) => {
  const host = sdk.MultiHost.of(effects, peerHostId)
  const origin = await host.bindPort(peerPort, {
    protocol: null,
    addSsl: null,
    preferredExternalPort: peerPort,
    secure: { ssl: false },
  })
  const peer = sdk.createInterface(effects, {
    name: 'XBT Lightning Peer',
    id: peerInterfaceId,
    description: 'Encrypted Lightning peer connections on the XBT chain.',
    type: 'p2p',
    masked: false,
    schemeOverride: null,
    username: '',
    path: '',
    query: {},
  })
  return [await origin.export([peer])]
})
