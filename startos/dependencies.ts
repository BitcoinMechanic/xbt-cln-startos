import { sdk } from './sdk'
import { backends, selectedBackend } from './backend'

export const setDependencies = sdk.setupDependencies(async ({ effects }) => {
  const packageId = await selectedBackend(effects)
  return { [packageId]: {
    healthChecks: [...backends[packageId].healthChecks],
    kind: 'running' as const,
    versionRange: packageId === 'knots-blake2b' ? '>=29.4.3:1' : '*', // Requires the BLAKE2b-capable fetching proxy.
  } }
})
