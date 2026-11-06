import { VersionGraph } from '@start9labs/start-sdk'
import { current } from './current'
import { v2 } from './v2'
export const versionGraph = VersionGraph.of({ current, other: [v2] })
