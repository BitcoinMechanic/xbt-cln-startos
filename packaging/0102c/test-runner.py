#!/usr/bin/env python3
"""Runner metadata regression only; synthetic IDs, no Docker or funded claims."""
import copy
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

B=Path(__file__).resolve().parent
# Optional baseline lets the release check prove these tests detect 0102's bug.
runner_path=Path(sys.argv.pop(1)) if len(sys.argv)>1 and not sys.argv[1].startswith('-') else B/'run.py'
spec=importlib.util.spec_from_file_location('candidate_runner',runner_path)
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def fixture():
    # Minimal consumer fixture transcribed from the retained validators:
    # 0101/runtime_evidence.py -> 0099/runtime_evidence.py ->
    # 0097/verified/runtime_result.py -> 0095/runtime_evidence.py ->
    # 0093/runtime_evidence.py -> 0091/runtime_evidence.py.
    # In particular, 0095 requires compiled_0094 on the 0094a envelope.
    # These are test values, not evidence of a real build or payment.
    candidate=dict(milestone='0090b',engine_sha256='a'*64,
                   images=dict(node='sha256:'+'b'*64,ui='sha256:'+'c'*64))
    startos=dict(milestone='0091',candidate_build=candidate)
    admin=dict(milestone='0092a',historical_evidence=startos)
    compiled=dict(historical_evidence=admin,backend_sha256='d'*64)
    deadline=dict(milestone='0094a',compiled_0094=compiled)
    retirement=dict(milestone='0096a',prior_0094a=deadline)
    runtime=dict(milestone='0098a',prior_0096a=retirement)
    return dict(milestone='0100',retained_0098a=runtime),candidate


class StopBeforeDocker(Exception):
    pass


class RetainedBuildTests(unittest.TestCase):
    def test_original_build_resolved_through_compiled_envelope_without_mutation(self):
        evidence,candidate=fixture();before=copy.deepcopy(evidence)
        self.assertIs(runner.old_candidate(evidence),candidate)
        self.assertEqual(evidence,before)

    def test_missing_compiled_envelope_does_not_use_misnested_fallback(self):
        evidence,_=fixture()
        deadline=evidence['retained_0098a']['prior_0096a']['prior_0094a']
        deadline['historical_evidence']=deadline.pop('compiled_0094')['historical_evidence']
        with self.assertRaisesRegex(RuntimeError,'compiled_0094'):
            runner.old_candidate(evidence)

    def test_missing_candidate_is_reported_at_its_exact_path(self):
        evidence,_=fixture()
        admin=evidence['retained_0098a']['prior_0096a']['prior_0094a']['compiled_0094']['historical_evidence']
        del admin['historical_evidence']['candidate_build']
        with self.assertRaisesRegex(RuntimeError,'candidate_build'):
            runner.old_candidate(evidence)

    def test_wrong_build_cannot_replace_original_0090b(self):
        evidence,candidate=fixture();candidate['milestone']='0090a'
        with self.assertRaisesRegex(RuntimeError,'0090b'):
            runner.old_candidate(evidence)

    def test_pack_selects_original_ui_before_docker_work(self):
        evidence,candidate=fixture()
        with patch.object(runner,'tag',side_effect=StopBeforeDocker) as tag:
            with self.assertRaises(StopBeforeDocker):
                runner.pack(None,None,None,evidence,None,None,None)
        tag.assert_called_once_with(candidate['images']['ui'],'accepted-xbt-ui')

    def test_bootstrap_harness_selects_original_node_before_build(self):
        evidence,candidate=fixture();calls=[]
        def tag(image,label):
            calls.append((image,label))
            if label=='accepted-node-before':raise StopBeforeDocker
            return 'synthetic-test-image'
        with tempfile.TemporaryDirectory() as tmp:
            context=Path(tmp)
            for repo in runner.REPOS.values():
                for phase in ('regression','live'):(context/repo/phase).mkdir(parents=True)
            scripts=context/'swap-controller-startos/scripts';scripts.mkdir()
            for name in ('test-migration-actions.cjs','test-live-actions.cjs',
                         'migration-action-fixture.cjs','test-migration-process.py'):
                (scripts/name).write_text('synthetic metadata test\n')
            (context/'lightning/tools/swap').mkdir(parents=True)
            (context/'swap-controller-startos/migration').mkdir()
            with patch.object(runner,'tag',side_effect=tag):
                with self.assertRaises(StopBeforeDocker):
                    runner.harness(context,None,evidence,{})
        self.assertEqual(calls,[(candidate['images']['node'],'accepted-node-before')])


if __name__=='__main__':unittest.main()
