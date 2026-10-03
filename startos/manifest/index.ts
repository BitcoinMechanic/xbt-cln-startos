import { setupManifest } from '@start9labs/start-sdk'
const short = { en_US: 'Experimental Lightning node for the XBT BLAKE2b chain' }
const long = {
  en_US:
    'Fresh-wallet observation build. Requires BLAKE2b Knots. Do not fund this package or migrate existing wallets yet. UI and swap coordinator roles are not enabled. Bounded force-close recovery is experimental and requires validation before live funding.',
}
const depBitcoindDescription = {
  en_US:
    'BLAKE2b Knots is required; the shared bitcoind package ID does not establish chain identity.',
}

export const manifest = setupManifest({
  id: 'xbt-cln',
  title: 'XBT Core Lightning',
  license: 'mit',
  packageRepo: 'https://github.com/BitcoinMechanic/xbt-cln-startos',
  upstreamRepo: 'https://github.com/BitcoinMechanic/lightning',
  marketingUrl: 'https://github.com/BitcoinMechanic/lightning',
  donationUrl: null,
  description: { short, long },
  volumes: ['main'],
  virtualNetworking: true,
  images: {
    lightning: {
      source: {
        dockerBuild: {
          dockerfile: 'Dockerfile.xbt',
          workdir: '.',
        },
      },
      arch: ['x86_64', 'aarch64'],
      emulateMissingAs: 'aarch64',
    },
  },
  dependencies: {
    bitcoind: {
      description: depBitcoindDescription,
      optional: false,
      metadata: {
        title: 'Bitcoin Knots (BLAKE2b)',
        icon: 'https://raw.githubusercontent.com/Start9Labs/bitcoin-core-startos/feec0b1dae42961a257948fe39b40caf8672fce1/dep-icon.svg',
      },
    },
  },
})
