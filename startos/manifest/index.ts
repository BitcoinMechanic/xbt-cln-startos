import { setupManifest } from '@start9labs/start-sdk'
import { depBitcoindDescription, long, short } from './i18n'

export const manifest = setupManifest({
  id: 'xbt-cln',
  title: 'XBT Core Lightning',
  license: 'mit',
  packageRepo: 'https://github.com/BitcoinMechanic/xbt-cln-startos',
  upstreamRepo: 'https://github.com/BitcoinMechanic/lightning',
  marketingUrl: 'https://blockstream.com/lightning',
  donationUrl: null,
  description: { short, long },
  volumes: ['main', 'public'],
  images: {
    lightning: {
      source: {
        dockerBuild: {
          dockerfile: 'Dockerfile.live',
          workdir: '.',
        },
      },
      arch: ['x86_64', 'aarch64'],
      emulateMissingAs: 'aarch64',
    },
    ui: {
      source: {
        dockerBuild: {
          dockerfile: 'Dockerfile.ui',
          workdir: '.',
        },
      },
      arch: ['x86_64', 'aarch64'],
      emulateMissingAs: 'aarch64',
    },
  },
  dependencies: {
    'knots-blake2b': {
      description: depBitcoindDescription, optional: true,
      metadata: { title: 'Bitcoin Knots (BLAKE2b)', icon: 'https://raw.githubusercontent.com/paulscode/knots-blake2b-startos/3847fce974be7d944f37f97e47b3851444c9ffc5/icon.png' },
    },
    bitcoind: {
      description: depBitcoindDescription,
      optional: true,
      metadata: {
        title: 'Bitcoin Knots (BLAKE2b)',
        icon: 'https://raw.githubusercontent.com/Start9Labs/bitcoin-core-startos/feec0b1dae42961a257948fe39b40caf8672fce1/dep-icon.svg',
      },
    },
  },
})
