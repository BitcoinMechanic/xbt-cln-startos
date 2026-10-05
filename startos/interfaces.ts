import { sdk } from './sdk'
import { peerPort, clnrestPort } from './utils'

export const controllerHostId = 'controller-rpc'
export const controllerInterfaceId = 'controller-rpc'

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
  const controllerHost = sdk.MultiHost.of(effects, controllerHostId)
  // SDK http bindings use secure:null; StartOS adds TLS at the platform edge.
  // The container speaks HTTP only on the internal service network.
  const controllerOrigin = await controllerHost.bindPort(clnrestPort, {
    protocol: 'http',
    preferredExternalPort: clnrestPort,
    addSsl: { preferredExternalPort: clnrestPort, addXForwardedHeaders: false },
  })
  const controller = sdk.createInterface(effects, {
    name: 'XBT Controller RPC', id: controllerInterfaceId,
    description: 'Use HTTPS and a separate restricted Rune header. No credentials are included in this URL.',
    type: 'api', masked: true, schemeOverride: null, username: null,
    path: '', query: {},
  })
  return [await origin.export([peer]), await controllerOrigin.export([controller])]
})
