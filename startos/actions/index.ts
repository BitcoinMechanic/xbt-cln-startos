import { createActions } from '../live/actions'
import { sdk } from '../sdk'
import { experimental } from './config/experimental'
import { config } from './config/config'
import { plugins } from './config/plugins'
import { watchtower } from './watchtower/watchtower'
import { createRune } from './generateRune'
import { revokeRunes } from './revokeRunes'
import { deleteGossipStore } from './deleteGossipStore'
import { resetPassword } from './resetPassword'
import { watchtowerInfo } from './watchtower/watchtowerInfo'
import { watchtowerClientInfo } from './watchtower/watchtowerClientInfo'
import { rescanBlockchain } from './rescanBlockchain'
import { nodeInfo } from './nodeInfo'
import { displaySeed } from './displaySeed'

const nodeActions = sdk.Actions.of()
  .addAction(config)
  .addAction(displaySeed)
  .addAction(experimental)
  .addAction(createRune)
  .addAction(revokeRunes)
  .addAction(deleteGossipStore)
  .addAction(resetPassword)
  .addAction(rescanBlockchain)
  .addAction(nodeInfo)

// @TODO generate-lnlink

export const actions = createActions(undefined, nodeActions)
