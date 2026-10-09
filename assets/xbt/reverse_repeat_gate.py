"""Routed repeat extension around the unchanged, pinned reverse gate journal.

The existing live gate opt-in and all older quote profiles remain intact.
Only the new register method admits the direction-scoped repeat contract.
"""
import json
import sys
import time
from reverse_gate import Gate as OriginalGate
from quote_plugin import save
from reverse_contract import REPEAT, incoming_pins, require, validate_terms


class Gate(OriginalGate):
    def handle(self, request):
        method=request.get('method');params=request.get('params',{})
        def result(value):return [dict(jsonrpc='2.0',id=request['id'],result=value)]
        def argument(index,key):return params[index] if isinstance(params,list) else params[key]
        if method=='getmanifest':
            replies=super().handle(request)
            replies[0]['result']['rpcmethods'].extend([
                dict(name='reverse-repeat-register',usage='quote',description='Register one routed reverse contract'),
                dict(name='reverse-retire-repeat',usage='payment_hash',description='Permanently retire an unpaid repeat quote')])
            return replies
        if method in ('reverse-repeat-register','reverse-retire-repeat'):
            require(self.active,'reverse_gate_inactive')
            if method=='reverse-repeat-register':
                terms=validate_terms(argument(0,'quote'));h=terms['payment_hash']
                old=self.quotes.get(h)
                if old:require(old['terms']==terms,'immutable_reverse_quote')
                else:
                    now=int(time.time())
                    require(now<terms['expires_at']<=now+120,'reverse_quote_expiry')
                    require(not any(e['phase']=='held' or (e['phase']=='quoted' and e['terms']['expires_at']>now)
                            for e in self.quotes.values()),'another_reverse_quote_active')
                    self.quotes[h]=dict(terms=terms,phase='quoted');save(self.path,self.quotes)
                return result(dict(registered=True))
            h=argument(0,'payment_hash');entry=self.quotes[h]
            require(entry['terms'].get('pilot')==REPEAT and entry['phase'] in ('quoted','expired')
                    and entry.get('binding') is None and entry['terms']['expires_at']<=int(time.time()),'retirement_refused')
            entry['phase']='expired';save(self.path,self.quotes)
            return result(dict(retired=True))
        if method=='htlc_accepted':
            entry=self.quotes.get(params.get('htlc',{}).get('payment_hash'))
            if entry and entry['terms'].get('pilot')==REPEAT and entry['phase']=='quoted':
                # Approval is limited to the original channel set, even before
                # the committed HTLC is durably pinned by the node authority.
                require(validate_terms(entry['terms']),'invalid_reverse_terms')
                if params['htlc'].get('short_channel_id') not in {p['short_channel_id'] for p in incoming_pins(entry['terms']['contract'])}:
                    return result(dict(result='fail',failure_message='2002'))
        replies=super().handle(request)
        if method=='reverse-pilot-info' and self.live:
            replies[0]['result']['repeat_profile']=REPEAT
        return replies


def main(path,live=True):
    gate=Gate(path,live=live)
    for line in sys.stdin:
        if not line.strip():continue
        request=json.loads(line)
        try:replies=gate.handle(request)
        except (ValueError,KeyError,TypeError,IndexError):
            if request.get('method')=='htlc_accepted':continue
            replies=[dict(jsonrpc='2.0',id=request['id'],error=dict(code=-32602,message='Reverse gate request refused.'))]
        for reply in replies:print(json.dumps(reply),end='\n\n',flush=True)
