import { sdk } from './sdk'
import { backends, selectedBackend } from './backend'
import { depBitcoindDescription } from './manifest/i18n'

export const dependencies = sdk.Dependencies.of()
  .addDependency(
    sdk.Dependency.optional('knots-blake2b', {
      description: depBitcoindDescription,
      metadata: {
        title: 'Bitcoin Knots (BLAKE2b)',
        icon: 'https://raw.githubusercontent.com/paulscode/knots-blake2b-startos/3847fce974be7d944f37f97e47b3851444c9ffc5/icon.png',
      },
      kind: 'running',
      versionRange: '>=29.4.3:1',
      healthChecks: [...backends['knots-blake2b'].healthChecks],
      enabled: async ({ effects }) =>
        (await selectedBackend(effects)) === 'knots-blake2b',
    }),
  )
  .addDependency(
    sdk.Dependency.optional('bitcoind', {
      description: depBitcoindDescription,
      metadata: {
        title: 'Bitcoin',
        icon: 'https://raw.githubusercontent.com/Start9Labs/bitcoin-core-startos/feec0b1dae42961a257948fe39b40caf8672fce1/dep-icon.svg',
      },
      kind: 'running',
      versionRange: '*',
      healthChecks: [...backends.bitcoind.healthChecks],
      enabled: async ({ effects }) =>
        (await selectedBackend(effects)) === 'bitcoind',
    }),
  )
