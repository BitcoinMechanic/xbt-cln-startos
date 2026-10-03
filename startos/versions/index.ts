import { VersionGraph } from '@start9labs/start-sdk'
import { current } from './current'

// A new package identity: never run Bitcoin CLN migrations on this wallet.
export const versionGraph = VersionGraph.of({ current, other: [] })
