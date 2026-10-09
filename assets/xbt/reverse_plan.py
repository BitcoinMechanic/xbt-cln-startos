"""Read-only, invoice-bound route planning. No send, pay, retry or shared layers."""
import json
import subprocess
from reverse_contract import require, validate_route, ROUTE_LIMITS
from route_math import plan_with_hints


def plan(rpc, invoice, source, *, max_delay=80):
    require(type(max_delay) is int and max_delay in ROUTE_LIMITS.values(), 'invalid_route_limit')
    require(type(invoice) is str and invoice.startswith('lnbc') and len(invoice)<=16384, 'invalid_invoice')
    d=rpc('decode',string=invoice)
    require(d.get('valid') is True and d.get('type')=='bolt11 invoice' and d.get('currency')=='bc'
            and type(d.get('amount_msat')) is int and d['amount_msat']==1500000
            and type(d.get('min_final_cltv_expiry')) is int and 1<=d['min_final_cltv_expiry']<=40,
            'invalid_recipient_invoice')
    policy=dict(source=source,destination=d['payee'],max_fee_msat=10000,max_delay=max_delay,max_hops=4,final_cltv=40)
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
        hops,_=plan_with_hints([],1500000,policy,d.get('routes',[]),query,_inspection=True)
    except subprocess.CalledProcessError:raise ValueError('bounded_route_unavailable') from None
    return validate_route(hops,source,d['payee'],max_delay=max_delay)
