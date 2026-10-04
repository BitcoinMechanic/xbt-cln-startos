import { sdk } from '../sdk'
import { nodeInfo } from './nodeInfo'
import { recoveryScanStart } from './recoveryScanStart'

import { finishEmptyRecovery } from './finishEmptyRecovery'

import { depositAddress, walletFunds, withdrawalStatus, prepareWithdrawal, sendWithdrawal, cancelWithdrawal } from './wallet'

import { connectPeer, channelStatus, openChannel, closeChannel } from './channels'

// Bounded wallet and single private-channel pilots; no Lightning-spending UI.
export const actions = sdk.Actions.of().addAction(nodeInfo).addAction(recoveryScanStart).addAction(finishEmptyRecovery)
  .addAction(depositAddress).addAction(walletFunds).addAction(withdrawalStatus)
  .addAction(prepareWithdrawal).addAction(sendWithdrawal).addAction(cancelWithdrawal)

  .addAction(connectPeer).addAction(channelStatus).addAction(openChannel).addAction(closeChannel)
