#!/usr/bin/env python3
"""Preparation only. This receipt is never permission to activate a swap gate."""
import fcntl
import json
import os
from pathlib import Path
import sys
from empty_backup import atomic_json
from recovery import load
from wallet_actions import Wallet, require

SOURCE = '81ba4099a63e5a0e83f55cead53c54f2a1b3c1fe'
RECORD = 'coordinator-preparation.json'


def check_bundle(directory):
    directory = Path(directory)
    require((directory / 'SOURCE_COMMIT').read_text().strip() == SOURCE,
            'Swap source revision mismatch')
    for name in ('reverse_gate.py', 'quote_plugin.py', 'reverse_activation.py'):
        require((directory / name).is_file(), 'Swap module missing')


class Preparation(Wallet):
    def inspect(self, bundle='/usr/local/libexec/xbt-swap'):
        check_bundle(bundle)
        node = self.ready()
        channels = self.rpc('listpeerchannels')['channels']
        require(not any(c.get('htlcs') for c in channels), 'Pending HTLCs; wait before preparation')
        expected = {'schema': 1, 'scope': 'preparation-only', 'node_id': node,
                    'network': self.network, 'source_commit': SOURCE}
        saved = os.path.lexists(self.root / RECORD)
        if saved:
            require(load(self.root, RECORD) == expected, 'Preparation binding changed; inspect locally')
        return expected, {'prepared': saved, 'source_commit': SOURCE,
                          'controller_pairing_required': True,
                          'live_activation_enabled_by_package': False,
                          'payment_started': False}

    def prepare(self, confirmed, bundle='/usr/local/libexec/xbt-swap'):
        require(confirmed is True, 'Explicit preparation confirmation required')
        expected, status = self.inspect(bundle)
        if not status['prepared']:
            atomic_json(self.root, RECORD, expected)
        return dict(status, prepared=True)


def main():
    try:
        root = Path(sys.argv[1])
        request = json.load(sys.stdin)
        # Share the wallet-action lock: preparation cannot overlap package wallet actions.
        with (root / 'wallet-pilot.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            worker = Preparation(root)
            if request.get('operation') == 'status':
                result = worker.inspect()[1]
            elif request.get('operation') == 'prepare':
                result = worker.prepare(request.get('confirmed'))
            else:
                raise ValueError('Unknown preparation operation')
        print(json.dumps(result))
    except Exception:
        print(json.dumps({'error': 'Coordinator preparation unavailable; inspect node health and recovery status. No gate was activated.'}))
        raise SystemExit(1)


if __name__ == '__main__':
    main()
