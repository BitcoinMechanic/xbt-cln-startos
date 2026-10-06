"""Dedicated read-only candidate inspection, separate from monitor and gates."""
from controller_credential import Credentials, main

class InspectionCredentials(Credentials):
    record_name = 'controller-inspection-read-only.json'
    restrictions = [['method=decode', 'method=getinfo', 'method=listfunds',
                     'method=listpeerchannels', 'method=listsendpays']]

if __name__ == '__main__':
    main(InspectionCredentials, 'controller-inspection-read-only.lock')
