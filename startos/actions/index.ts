import { coordinatorStatus, prepareCoordinator } from './coordinator'
import { createInvoice, invoiceStatus, reviewPayment, payInvoice, paymentStatus } from './lightning'
import { sdk } from '../sdk'
import { nodeInfo } from './nodeInfo'
import { recoveryScanStart } from './recoveryScanStart'

import { finishEmptyRecovery } from './finishEmptyRecovery'

import { depositAddress, walletFunds, withdrawalStatus, prepareWithdrawal, sendWithdrawal, cancelWithdrawal } from './wallet'

import { connectPeer, channelStatus, openChannel, closeChannel, archiveChannel } from './channels'

// Bounded wallet, channel and Lightning payment actions.
export const actions = sdk.Actions.of().addAction(nodeInfo).addAction(recoveryScanStart).addAction(finishEmptyRecovery)
  .addAction(depositAddress).addAction(walletFunds).addAction(withdrawalStatus)
  .addAction(prepareWithdrawal).addAction(sendWithdrawal).addAction(cancelWithdrawal)

  .addAction(connectPeer).addAction(channelStatus).addAction(openChannel).addAction(closeChannel).addAction(archiveChannel)

  .addAction(createInvoice).addAction(invoiceStatus).addAction(reviewPayment).addAction(payInvoice).addAction(paymentStatus)

  .addAction(coordinatorStatus).addAction(prepareCoordinator)
