import market_terms as mt
"""Read-only, invoice-bound route planning. No send, pay, retry or shared layers."""
import json
import subprocess
from pilot_contract import require, validate_route
from route_math import plan_with_hints


def plan(rpc, invoice, source, *, market_limits=None):
    require(type(invoice) is str and invoice.startswith('lnxbt') and len(invoice)<=16384, 'invalid_recipient_invoice')
    d=rpc('decode',string=invoice)
    require(d.get('valid') is True and d.get('type')=='bolt11 invoice' and d.get('currency')=='xbt'
            and type(d.get('amount_msat')) is int and (d['amount_msat']==2000000 if market_limits is None else 0<d['amount_msat']<=mt.limits(market_limits)['max_xbt_msat'] and d['amount_msat']%1000==0)
            and type(d.get('min_final_cltv_expiry')) is int and 1<=d['min_final_cltv_expiry']<=40,
            'invalid_recipient_invoice')
    policy=dict(source=source,destination=d['payee'],max_fee_msat=10000,max_delay=80,max_hops=4,final_cltv=40)
    def query(cli,method,*args):
        require(method=='getroutes','route_method_refused')
        params={}
        for arg in args:
            k,v=arg.split('=',1)
            params[k]=v if k in ('source','destination') else json.loads(v)
        try:return rpc('getroutes',**params)
        except ValueError as error:
            if getattr(error,'code',None) not in (205,206):raise
            raise subprocess.CalledProcessError(1, ['getroutes'], output=json.dumps({'code':error.code})) from None
    try:
        hops,_=plan_with_hints([],d['amount_msat'],policy,d.get('routes',[]),query,_inspection=True,_xbt_inspection=True)
    except subprocess.CalledProcessError:raise ValueError('bounded_route_unavailable') from None
    return validate_route(hops,source,d['payee'],recipient_amount=d['amount_msat'])
