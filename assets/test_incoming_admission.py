import copy,threading,unittest
from unittest.mock import Mock
import customer_invoice as invoice
import customer_plugin as plugin

class Tests(unittest.TestCase):
    def setUp(self):
        self.pin={'peer_id':'02'+'11'*32}
        self.row=dict(peer_connected=True,reestablished=True,htlcs=[],receivable_msat=100000000,
            features=['option_anchors'],feerate={'perkw':1255},dust_limit_msat=546000,
            private=True,alias={'remote':'123x2x1'},updates={'remote':dict(htlc_minimum_msat=1,
                htlc_maximum_msat=100000000,fee_base_msat=1000,fee_proportional_millionths=0,cltv_expiry_delta=80)})
        self.authority=Mock();self.authority.channel.side_effect=lambda pin:self.row
    def hints(self,amount):
        return invoice.select_hints(self.authority,{'amount_msat':amount,'approved_channels':[self.pin]})
    def test_dust_boundary_unchanged_and_actionable(self):
        for amount in (39000,546000):
            with self.assertRaises(invoice.AdmissionError) as caught:self.hints(amount)
            self.assertEqual(str(caught.exception),'incoming_amount_below_safe_minimum')
            self.assertEqual(caught.exception.details,{'amount_msat':amount,'minimum_msat':546001})
        self.assertEqual(len(self.hints(546001)),1)
        self.assertEqual(len(self.hints(4000000)),1)
    def test_non_anchor_fee_in_minimum(self):
        self.row['features']=[]
        minimum=546000+((703*1255+999)//1000)*1000+1
        with self.assertRaises(invoice.AdmissionError) as caught:self.hints(minimum-1)
        self.assertEqual(caught.exception.details['minimum_msat'],minimum)
        self.assertEqual(len(self.hints(minimum)),1)
    def test_other_refusals_explained(self):
        for changes,reason in [({'peer_connected':False},'incoming_channel_disconnected'),
                               ({'htlcs':[{}]},'incoming_channel_busy'),
                               ({'receivable_msat':0},'incoming_liquidity_insufficient'),
                               ({'updates':{}},'incoming_htlc_policy_limit'),
                               ({'alias':{},'features':['option_anchors','option_scid_alias']},'incoming_hint_unavailable')]:
            previous=copy.deepcopy(self.row);self.row.update(changes)
            with self.assertRaisesRegex(invoice.AdmissionError,reason):self.hints(4000000)
            self.row=previous
    def test_safe_inspect_envelope_never_mutation_retry(self):
        error=invoice.AdmissionError('incoming_amount_below_safe_minimum',amount_msat=39000,minimum_msat=546001)
        service=plugin.Service.__new__(plugin.Service);service.serial=threading.RLock();service._invoke=Mock(side_effect=error)
        self.assertEqual(service.invoke(plugin.remote.CALL,{'operation':'inspect'}),{'admission_error':str(error),'admission_details':error.details})
        for op in ('enroll','send','release'):
            with self.assertRaises(invoice.AdmissionError):service.invoke(plugin.remote.CALL,{'operation':op})
        self.assertEqual(service._invoke.call_count,4)
if __name__=='__main__':unittest.main()
