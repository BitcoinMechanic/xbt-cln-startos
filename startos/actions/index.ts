import { sdk } from '../sdk'
import { nodeInfo } from './nodeInfo'
import { recoveryScanStart } from './recoveryScanStart'

import { finishEmptyRecovery } from './finishEmptyRecovery'

import { depositAddress, walletFunds, withdrawalStatus, prepareWithdrawal, sendWithdrawal, cancelWithdrawal } from './wallet'

// Bounded on-chain pilot; no channel-opening or Lightning-spending actions.
export const actions = sdk.Actions.of().addAction(nodeInfo).addAction(recoveryScanStart).addAction(finishEmptyRecovery)
  .addAction(depositAddress).addAction(walletFunds).addAction(withdrawalStatus)
  .addAction(prepareWithdrawal).addAction(sendWithdrawal).addAction(cancelWithdrawal)
