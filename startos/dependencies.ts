import { sdk } from './sdk'
import { backends, selectedBackend } from './backend'

export const setDependencies = sdk.setupDependencies(async ({ effects }) => {
  const packageId = await selectedBackend(effects)
  return { [packageId]: {
    healthChecks: [...backends[packageId].healthChecks],
    kind: 'running' as const,
    versionRange: '*', // Runtime identity checks still authenticate the chain.
  } }
})
