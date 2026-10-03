import { sdk } from '../sdk'
import { nodeInfo } from './nodeInfo'

// Observation build: no spending, plugin, wallet-import or recovery actions.
export const actions = sdk.Actions.of().addAction(nodeInfo)
