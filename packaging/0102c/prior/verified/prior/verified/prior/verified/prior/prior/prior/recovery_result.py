"""Strict recovery receipt; amount fields vary with real mined fees."""
import json


def require(ok, reason):
    if not ok: raise RuntimeError(reason)


def fixed():
    return dict(schema=1, fixture='packaged-xbt-recovery-0088', regtest_only=True, installer=False,
        channels=2, channel_roles=['opener', 'recipient'], original_identity=True,
        database_excluded=True, exact_package_hooks=True, exact_package_commands=True,
        post_backup_payments=2, interrupted_recovery=True, repeated_emergency_recovery=True, high_address_negative_control=True,
        high_address_types=['bech32', 'p2tr'], address_window=10000, full_rescan=True,
        channels_terminal=True, resolved_restart=True, ui_password_and_withdrawal=True,
        unified_withdrawals=3, default_fee_withdrawals=3, deposited_sats=1435801,
        startos_supervisor_tested=False, live_migration=False)


def validate(result):
    monetary = {'drained_sats', 'mining_fees_sats', 'unspent_anchor_sats'}
    require(type(result) is dict and set(result) == set(fixed()) | monetary, 'Recovery receipt fields differ')
    require(json.dumps({k:result[k] for k in fixed()}, sort_keys=True) == json.dumps(fixed(), sort_keys=True),
            'Recovery matrix incomplete or scope inflated')
    require(all(type(result[k]) is int for k in monetary), 'Invalid recovery amounts')
    require(result['drained_sats'] > 1300000 and 0 < result['mining_fees_sats'] < 50000 and
            result['unspent_anchor_sats'] in (0,330,660,990,1320), 'Recovery amounts out of bounds')
    require(result['deposited_sats'] == sum(result[k] for k in monetary), 'Recovery amount reconciliation differs')
