#!/usr/bin/env python3
"""Package manifest boundaries; native SDK evaluation is run separately."""
import copy,unittest
from pathlib import Path
import run as r
checks=r.module(Path(__file__).with_name('package-checks.py'),'package_checks_test')

def sample(asset='controller'):
    names=['controller'] if asset=='controller' else ['lightning','ui']
    m=dict(id='swap-controller' if asset=='controller' else 'xbt-cln',version='test',osVersion='test',sdkVersion='2.0.9',
           canMigrateTo='test',canMigrateFrom='test',volumes=['main'],hardwareRequirements={'arch':['x86_64']},
           images={n:dict(source={'dockerTag':'sha256:'+'a'*64},arch=['x86_64'],emulateMissingAs=None,nvidiaContainer=False) for n in names},dependencies={})
    if asset!='controller':m['dependencies']['bitcoind']=dict(optional=False,description={'en_US':'backend'},metadata=dict(title='Bitcoin Knots (BLAKE2b)',icon=checks.ICON_URL))
    p=copy.deepcopy(m)
    for image in p['images'].values():image.update(source='packed',emulateMissing=False);del image['emulateMissingAs']
    for row in p['dependencies'].values():row['metadata']=None
    return m,p

class PackageTests(unittest.TestCase):
    def test_input_native_policy_passes(self):
        m,_=sample();checks.images(m,'controller',{'controller':m['images']['controller']['source']})

    def test_original_sdk_emulation_default_is_rejected(self):
        m,p=sample()
        for target in (m,p):
            target['images']['controller']['emulateMissingAs']='x86_64'
            with self.assertRaisesRegex(RuntimeError,'emulation'):
                checks.images(target,'controller',{'controller':target['images']['controller']['source']})

    def test_packed_controller_passes_strict_image_policy(self):
        m,p=sample();checks.packed_manifest(p,m,'controller')

    def test_dependency_metadata_moved_to_archive_is_accepted(self):
        m,p=sample('xbt');checks.packed_manifest(p,m,'xbt')
        del p['dependencies']['bitcoind']['metadata'];checks.packed_manifest(p,m,'xbt')
        checks.dependency_files(m['dependencies']['bitcoind'],{'title':'Bitcoin Knots (BLAKE2b)'},checks.ICON_SHA256)

    def test_changed_dependency_requirement_is_refused(self):
        m,p=sample('xbt');p['dependencies']['bitcoind']['optional']=True
        with self.assertRaisesRegex(RuntimeError,'dependency contract'):checks.packed_manifest(p,m,'xbt')

    def test_optional_dependency_range_serialization(self):
        m,p=sample('xbt');p['dependencies']['bitcoind']['versionRange']=None
        checks.packed_manifest(p,m,'xbt')
        p['dependencies']['bitcoind']['versionRange']='>=1.0.0'
        with self.assertRaisesRegex(RuntimeError,'dependency contract'):checks.packed_manifest(p,m,'xbt')
        m['dependencies']['bitcoind']['versionRange']='>=1.0.0'
        checks.packed_manifest(p,m,'xbt')

    def test_external_dependency_metadata_is_refused(self):
        m,p=sample('xbt');p['dependencies']['bitcoind']['metadata']=m['dependencies']['bitcoind']['metadata']
        with self.assertRaisesRegex(RuntimeError,'not embedded'):checks.packed_manifest(p,m,'xbt')

    def test_changed_dependency_title_or_icon_is_refused(self):
        m,_=sample('xbt');row=m['dependencies']['bitcoind']
        for metadata,icon in [({'title':'different'},checks.ICON_SHA256),({'title':row['metadata']['title']},'0'*64)]:
            with self.assertRaises(RuntimeError):checks.dependency_files(row,metadata,icon)

    def test_architecture_and_unpacked_source_are_refused(self):
        m,p=sample()
        p['images']['controller']['arch']=['aarch64']
        with self.assertRaisesRegex(RuntimeError,'architecture'):checks.packed_manifest(p,m,'controller')
        p['images']['controller']['arch']=['x86_64'];p['images']['controller']['source']=m['images']['controller']['source']
        with self.assertRaisesRegex(RuntimeError,'Image source'):checks.packed_manifest(p,m,'controller')

    def test_controller_overlay_explicitly_disables_emulation(self):
        text="source: { dockerBuild: { dockerfile: 'Dockerfile.live', workdir: '.' } }, arch: ['x86_64']"
        bound=r.packaging_manifest_text(text,'controller','sha256:'+'a'*64)
        self.assertIn("arch: ['x86_64'], emulateMissingAs: null",bound)
        self.assertNotIn('dockerBuild',bound)

if __name__=='__main__':unittest.main()
