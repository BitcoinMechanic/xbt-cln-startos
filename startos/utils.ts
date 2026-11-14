export const uiPort = 4500
export const wsPort = 4269
export const rpcPort = 8080
export const peerPort = 9735
export const clnrestPort = 3010
export const watchtowerPort = 9814
export const websocketPort = 7272
export const grpcPort = 2106

export { rootDir, mainMounts } from './volume'
export const bitcoinDataDir = '/mnt/bitcoin'

/** Host path of the rune the CLN Application UI authenticates with. */
export const commandoEnv = '/media/startos/volumes/main/.commando-env'

// Retained export name for package consumers; resolves the selected backend.
export { backendRpcBridge as bitcoindRpcBridge } from './backend'
