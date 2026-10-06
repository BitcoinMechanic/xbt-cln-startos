"""Separate observation credential; no gate registration or resolution authority."""
from controller_credential import Credentials, main
from controller_credential import require
from gate import Gate

class GateCredentials(Credentials):
    record_name = 'controller-gate-read-only.json'
    restrictions = [['method=getinfo', 'method=reverse-pilot-info'], ['pnum=0']]

    def create(self, confirmed):
        require(confirmed is True, 'confirmation_required')
        status = Gate(self.root).status()
        require(status['active'] and not status['restored_gate_blocked'], 'active_gate_required')
        return super().create(confirmed)

if __name__ == '__main__':
    main(GateCredentials, 'controller-gate-read-only.lock')
