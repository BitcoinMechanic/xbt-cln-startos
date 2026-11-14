#!/usr/bin/env python3
"""Workspace and resume boundaries; isolated files and mocked CLI, no installers."""
import hashlib,json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import run as runner

resume=runner.module(Path(__file__).with_name('resume-pack.py'),'resume_tests')


class PackagingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root=self.base/'migration';self.root.mkdir()
        self.results=self.root/'build-results/run';self.results.mkdir(parents=True)

    def test_existing_parent_workspace_and_signing_key_are_reused(self):
        key=self.base/'.startos/build.key.pem';key.parent.mkdir();key.write_text('test signing identity')
        with patch.object(runner,'logged') as logged,patch.object(runner,'output',return_value='test-cli'):
            self.assertEqual(runner.packaging_workspace(self.root,self.results),self.base)
        logged.assert_called_once_with(['start-cli','s9pk','init-workspace'],self.results/'workspace-init.log',cwd=self.base)
        self.assertEqual(key.read_text(),'test signing identity')

    def test_missing_workspace_is_initialized_at_persistent_migration_root(self):
        def init(command,path,*,cwd):
            self.assertEqual(cwd,self.root)
            key=cwd/'.startos/build.key.pem';key.parent.mkdir();key.write_text('new test signing identity')
        with patch.object(runner,'logged',side_effect=init),patch.object(runner,'output',return_value='test-cli'):
            self.assertEqual(runner.packaging_workspace(self.root,self.results),self.root)
        self.assertTrue((self.root/'.startos/build.key.pem').is_file())
        self.assertFalse((self.results/'.startos').exists())

    def test_initializer_cannot_silently_change_existing_signing_key(self):
        key=self.root/'.startos/build.key.pem';key.parent.mkdir();key.write_text('existing test identity')
        def change(*args,**kwargs):key.write_text('different test identity')
        with patch.object(runner,'logged',side_effect=change):
            with self.assertRaisesRegex(RuntimeError,'signing key changed'):
                runner.packaging_workspace(self.root,self.results)

    def source_fixture(self):
        old=self.base/'old';fresh=self.base/'fresh';old.mkdir();fresh.mkdir()
        rel='swap-controller-startos/startos/manifest/index.ts'
        original="source: { dockerBuild: { dockerfile: 'Dockerfile.live', workdir: '.' } }, arch: ['x86_64', 'aarch64']"
        for root in (old,fresh):
            p=root/rel;p.parent.mkdir(parents=True);p.write_text(original)
        images={'controller-a':'sha256:'+'a'*64}
        source={'files':{rel:hashlib.sha256(original.encode()).hexdigest()}}
        return old,fresh,rel,source,images

    def test_already_bound_controller_manifest_resumes_without_changing_original(self):
        old,fresh,rel,source,images=self.source_fixture()
        bound=runner.bound_manifest_text((fresh/rel).read_text(),'controller',images['controller-a'])
        (old/rel).write_text(bound)
        resume.verify_source_inputs(runner,old,fresh,source,images,{})
        self.assertEqual((old/rel).read_text(),bound)
        self.assertIn('dockerBuild',(fresh/rel).read_text())

    def test_manifest_bound_to_another_image_is_refused(self):
        old,fresh,rel,source,images=self.source_fixture()
        (old/rel).write_text(runner.bound_manifest_text((fresh/rel).read_text(),'controller','sha256:'+'b'*64))
        with self.assertRaisesRegex(RuntimeError,'unexpected change'):
            resume.verify_source_inputs(runner,old,fresh,source,images,{})

    def test_other_source_edits_are_refused(self):
        old,fresh,rel,source,images=self.source_fixture()
        extra='swap-controller-startos/startos/index.ts';(old/extra).write_text('changed')
        source['files'][extra]=hashlib.sha256(b'original').hexdigest()
        with self.assertRaisesRegex(RuntimeError,'source input changed'):
            resume.verify_source_inputs(runner,old,fresh,source,images,{})

    def test_missing_completed_gate_is_refused(self):
        (self.results/'gates.json').write_text(json.dumps({'units':{}}))
        with self.assertRaisesRegex(RuntimeError,'Incomplete retained gate set'):
            resume.completed_gates(runner,self.results,{}, {})

    def test_summary_cannot_hide_a_failing_raw_unit_receipt(self):
        good=dict(tests=184,failures=0,errors=0,skipped=0)
        (self.results/'gates.json').write_text(json.dumps(dict(units=good,swaps={},actions={},bootstrap={})))
        (self.results/'checks').mkdir()
        (self.results/'checks/unit-result.json').write_text(json.dumps(dict(good,failures=1)))
        with self.assertRaisesRegex(RuntimeError,'Raw unit result differs'):
            resume.completed_gates(runner,self.results,{}, {})

    def test_retained_receipt_symlink_is_refused(self):
        target=self.base/'receipt.json';target.write_text('{}')
        (self.results/'gates.json').symlink_to(target)
        with self.assertRaisesRegex(RuntimeError,'symlinked retained input'):
            resume.completed_gates(runner,self.results,{}, {})


if __name__=='__main__':unittest.main()
