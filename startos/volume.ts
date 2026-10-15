import { sdk } from './sdk'
export const rootDir = '/root/.lightning'
export const mainMounts = sdk.Mounts.of().mountVolume({
  volumeId: 'main',
  subpath: null,
  mountpoint: rootDir,
  readonly: false,
})
