// Pure startup policy, shared with the offline wrapper tests.
export const activationHeight = 961640
export const activationHash =
  '0000000000000050c1e5f69672f459293be14f46e5a494e7a8c8541396f18eeb'

export function verifyBackend(chain: any, deployments: any, hash: string) {
  if (
    chain?.chain !== 'main' ||
    chain?.initialblockdownload !== false ||
    !Number.isSafeInteger(chain?.blocks) ||
    chain.blocks < activationHeight ||
    chain.pruned !== false ||
    deployments?.blake2b?.active !== true ||
    deployments.blake2b.height !== activationHeight ||
    hash.trim() !== activationHash
  ) {
    throw new Error(
      'XBT requires synced, unpruned BLAKE2b Knots with the pinned activation checkpoint',
    )
  }
}

export function nodeHealth(info: any) {
  if (info?.network !== 'xbt')
    return {
      result: 'failure' as const,
      message: 'Unexpected Lightning chain identity',
    }
  if (Object.keys(info).some((k) => k.startsWith('warning_')))
    return {
      result: 'loading' as const,
      message: 'XBT node is syncing or reports a warning',
    }
  return {
    result: 'success' as const,
    message: 'XBT RPC ready; bounded wallet and channel pilot',
  }
}
