"""Require the SDK path for every grant, pair, confirmation and invoice."""
import json
def validate(r):
    expected=dict(schema=1,fixture='startos-sdk-actions-0100',startos_host_acceptance=False,regtest_only=True,
        actual_sdk_forms=True,compiled_handlers=True,unchanged_runtime=True,closed_channels=0,installer=False)
    if type(r) is not dict or set(r)!=set(expected)|{'counts'} or json.dumps({k:r[k] for k in expected},sort_keys=True)!=json.dumps(expected,sort_keys=True):
        raise RuntimeError('Action receipt scope differs')
    counts=r['counts']
    minimum={'migrated-admin-init':4,'migrated-review-incoming':2,'migrated-review-outgoing':2,
        'migrated-grant-confirm':8,'migrated-grant-credential':8,'migrated-initialize':2,
        'migrated-status':6,'migrated-history':6,'migrated-invoice':10}
    for d in ('forward','reverse'):
        for a in ('pair','new','confirm'):minimum['migrated-'+a+'-'+d]=3
    if type(counts) is not dict or set(counts)!=set(minimum) or any(type(counts[k]) is not int or counts[k]<n for k,n in minimum.items()):
        raise RuntimeError('Missing real SDK action coverage')
