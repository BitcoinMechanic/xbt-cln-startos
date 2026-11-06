#!/usr/bin/env python3
"""Run authority/restore/service and real fixture-entry boundaries; VM skips are not acceptance."""
import argparse,json,os,sys,unittest
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('root',type=Path)
p.add_argument('--allow-socket-skip',action='store_true');p.add_argument('--receipt',type=Path)
a=p.parse_args()
paths=[str(a.root.resolve()/'lightning/tools/swap'),str(a.root.resolve()/'swap-controller-startos/migration')]
sys.path[:0]=paths
os.environ['PYTHONPATH']=os.pathsep.join(paths)
os.environ['PACKAGE_CONTROLLER_SOURCE']=paths[1]
names=['test_held_gate','test_bounded_authority','test_remote_authority','test_customer_invoice',
       'test_cross_worker','test_customer_https','test_coordinator_admin','test_restore_barrier',
       'test_service','test_coordinator_fixture',
       'test_deadline_protection','test_chain_recovery','test_deadline_fixture','test_onchain_retirement','test_package_runtime','test_live_policy']
r=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromNames(names))
ok=r.wasSuccessful() and (not r.skipped or (a.allow_socket_skip and len(r.skipped)==1
    and 'test_fresh_CLI_grants_and_renewal_using_real_local_socket' in r.skipped[0][0].id()))
if not ok:raise SystemExit('Unit acceptance failed; no funded or build claim.')
if a.receipt:a.receipt.write_text(json.dumps(dict(tests=r.testsRun,failures=0,errors=0,skipped=len(r.skipped)))+'\n')
