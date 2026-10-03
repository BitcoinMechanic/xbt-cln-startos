import { sdk } from '../sdk'
import { nodeInfo } from './nodeInfo'
import { recoveryScanStart } from './recoveryScanStart'

import { finishEmptyRecovery } from './finishEmptyRecovery'

// No spending actions; stopped-service scan adjustment is restricted to empty restores.
export const actions = sdk.Actions.of().addAction(nodeInfo).addAction(recoveryScanStart).addAction(finishEmptyRecovery)
