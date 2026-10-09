"""Append bounded, one-hop incoming hints to our unsigned BOLT11 invoice.

Only current approved local channels with an observed remote fee/CLTV policy
are advertised. A hint is reachability information, not payment authority.
"""
import re
from reverse_contract import incoming_pins, pin_matches, require


def hint_scid(ch):
    # Match pinned CLN routehint.c: a negotiated alias channel must never
    # advertise its funding SCID. REMOTE is the identifier our peer accepts
    # when reverseing toward us; LOCAL belongs to the opposite direction.
    features=ch.get('features',[]);aliases=ch.get('alias',{})
    require(type(features) is list and all(type(f) is str for f in features)
            and type(aliases) is dict,'invalid_channel_alias_metadata')
    remote=aliases.get('remote')
    if 'option_scid_alias' in features:
        scid=remote
    elif ch.get('private') is True and remote is not None:
        scid=remote
    else:
        scid=ch.get('short_channel_id')
    if type(scid) is not str or not re.fullmatch(r'[0-9]{1,8}x[0-9]{1,8}x[0-9]{1,5}',scid):
        return None
    if any(value>=limit for value,limit in zip(map(int,scid.split('x')),(2**24,2**24,2**16))):
        return None
    return scid


def hints(c, rows):
    result=[]
    for pin in incoming_pins(c):
        found=[ch for ch in rows if pin_matches(ch,pin)]
        require(len(found)==1,'channel_changed');ch=found[0]
        if ch.get('state')!='CHANNELD_NORMAL' or ch.get('peer_connected') is not True or ch.get('receivable_msat',0)<3000000:
            continue
        scid=hint_scid(ch)
        if scid is None:continue
        p=ch.get('updates',{}).get('remote',{})
        keys=('fee_base_msat','fee_proportional_millionths','cltv_expiry_delta')
        if not all(type(p.get(k)) is int and 0<=p[k]<bound for k,bound in zip(keys,(2**32,2**32,2**16))):continue
        if not (p.get('htlc_minimum_msat',3000001)<=3000000<=p.get('htlc_maximum_msat',0)):continue
        result.append(dict(pubkey=pin['peer_id'],short_channel_id=scid,**{k:p[k] for k in keys}))
    require(result,'incoming_route_hints_unavailable')
    return result


def add(unsigned, routes):
    from swap_invoice import CHARSET, byte_words, encode
    hrp,payload=unsigned.rsplit('1',1)
    words=[CHARSET.index(c) for c in payload]
    require(words[-110:-6]==[0]*104 and 1<=len(routes)<=8,'invalid_unsigned_invoice')
    words=words[:-110]
    for hint in routes:
        parts=list(map(int,hint['short_channel_id'].split('x')))
        require(len(parts)==3 and all(0<=v<lim for v,lim in zip(parts,(2**24,2**24,2**16))),'invalid_hint_scid')
        scid=(parts[0]<<40)|(parts[1]<<16)|parts[2]
        raw=bytes.fromhex(hint['pubkey'])+scid.to_bytes(8,'big')
        raw+=hint['fee_base_msat'].to_bytes(4,'big')+hint['fee_proportional_millionths'].to_bytes(4,'big')+hint['cltv_expiry_delta'].to_bytes(2,'big')
        field=byte_words(raw);words.extend([CHARSET.index('r'),len(field)>>5,len(field)&31,*field])
    return encode(hrp,words+[0]*104)


def unsigned(payment_hash,secret,final_cltv):
    # Caller has checked the active identity-bound XBT gate and enrolled grant.
    # Limit the pinned encoder's explicit live opt-in to this single operation.
    from reverse_activation import ACTIVE
    from swap_invoice import unsigned_invoice
    token=ACTIVE.set(True)
    try:return unsigned_invoice(payment_hash,secret,3000000,120,currency='xbt',final_cltv=final_cltv,live_reverse=True)
    finally:ACTIVE.reset(token)
