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
      source: { ociLayout: { path: '.build-inputs/lightning-x86_64.tar' } },
      arch: ['x86_64'],
      emulateMissing: false,
    },
    ui: {
      source: { ociLayout: { path: '.build-inputs/ui-x86_64.tar' } },
      arch: ['x86_64'],
      emulateMissing: false,
    },
  },
})
