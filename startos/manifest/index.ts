import { setupManifest } from '@start9labs/start-sdk'
import { long, short } from './i18n'

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
    },
    ui: {
      source: {
        dockerBuild: {
          dockerfile: 'Dockerfile.ui',
          workdir: '.',
        },
      },
      arch: ['x86_64', 'aarch64'],
    },
  },
})
