"""Exact successful 0092a fixture schema, including populated restore tests."""
def service_expected():
    cases=[]
    for d in ('forward','reverse'):
        for n in ('release','fail','restart-held'):
            cases.append(dict(direction=d,scenario=n,state='failed' if n=='fail' else 'settled',automatic_worker=True,
                confirmed_before_enrollment=True,signed_customer_invoice=True,one_outgoing_attempt=True,
                original_contract_invoice_HTLC_attempt=True,exact_twelve_balances=True,
                SIGKILL_after_enrollment_invoice_send_resolution=True,service_pause_recovery=True,
                saved_markup_unchanged=True,history_count=('release','fail','restart-held').index(n)+1,
                both_chains_restarted=n=='restart-held',paused_expired_recovery=n=='restart-held',
                renewed_grants_preserve_history=n=='restart-held'))
    return dict(schema=1,fixture='privkeyio-service-0084',scenarios=cases,regtest_only=True,native_https=True,
        cached_offline_history=True,synthetic_price_snapshots=True,live_market_feed=False,
        startos_actions_registered=False,installer=False)


def expected():
    btc,xbt='btc-cln-v1','xbt-privkeyio-v1'
    roles=[(btc,'outgoing'),(btc,'incoming'),(xbt,'outgoing'),(xbt,'incoming'),
           (btc,'incoming'),(xbt,'outgoing'),(xbt,'incoming'),(btc,'outgoing')]
    grants=[dict(profile=p,kind=k,channel_count=1,review_without_authority=True,
                 fresh_process_confirmation=True,lost_reply_same_grant=True) for p,k in roles]
    return dict(schema=1,fixture='privkeyio-coordinator-admin-0092a',regtest_only=True,installer=False,
        grants=grants,restore=dict(coordinator_count=4,controller_count=2,stopped_fixture_journals=True,
            execution_refused_before_RPC=True,history_preserved=True,funded_wallet_restore=False,loaded_objects_refused=True,
            fresh_facade_startup_refused=True,populated_publishers=2,credential_journals=4),service=service_expected())


