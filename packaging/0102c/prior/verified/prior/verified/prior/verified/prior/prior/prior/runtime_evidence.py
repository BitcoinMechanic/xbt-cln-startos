"""Bind candidate build receipts to retained funded evidence; no live actions."""
import hashlib
import json
from pathlib import Path
import re
import zipfile

import common as cp
import recovery_runtime as recovery
import node_ui_runtime as node_ui

BUNDLE = Path(__file__).resolve().parent
INSTALLER = 'f090d53d1d1482fbd153db47d9dd2bf89e53c97ae21dcb561356144538b632d0'
PRIOR_INSTALLER = '4e838bb5298f41f0c75537a5829d33fad0590fb861ddd770795d56c94f95eb32'
PRIOR_EXPORT = '5fb19bec01bce509e04250d1f9790c673a88ad730d72fc98802385943d4d5eb6'
BASE_TAG = 'privkeyio-backup-recovery-20261012'
ENGINE = 'bb272c7a51c821558f0b623f563b2f0bc2d6d3bea2f175fc15e2f5206d6c1430'
require = recovery.require
same = recovery.same


def read(directory, name):
    path = cp.ordinary_path(directory, name)
    require(path.is_file() and path.stat().st_size < 8*1024*1024, 'Missing or oversized receipt: '+name)
    return json.loads(path.read_text())


def image_binding(images):
    text = (BUNDLE/'tested-manifest-input.ts').read_text()
    original = hashlib.sha256(text.encode()).hexdigest()
    for filename, image in [('Dockerfile', images['node']), ('Dockerfile.ui', images['ui'])]:
        pattern = r"source: \{\s+dockerBuild: \{\s+dockerfile: '" + re.escape(filename) + r"',\s+workdir: '\.',\s+\},\s+\}"
        text, count = re.subn(pattern, "source: { dockerTag: '"+image+"' }", text)
        require(count == 1, 'Tested manifest template changed')
    require(text.count("arch: ['x86_64', 'aarch64']") == 2 and
            text.count("emulateMissingAs: 'aarch64'") == 2, 'Tested architecture template changed')
    text = text.replace("arch: ['x86_64', 'aarch64']", "arch: ['x86_64']")
    text = text.replace("emulateMissingAs: 'aarch64'", 'emulateMissingAs: null')
    return dict(original_sha256=original, packaged_sha256=hashlib.sha256(text.encode()).hexdigest(),
        images=dict(lightning=images['node'], ui=images['ui']), architecture='x86_64', emulation=False)


def validate(e):
    require(type(e) is dict and set(e) == {'schema','milestone','candidate_build','prior_build','retained_regtest'},
            'Candidate evidence fields differ')
    same(e['schema'], 1, 'Evidence schema differs'); same(e['milestone'], '0091', 'Evidence milestone differs')
    recovery.validate(e['retained_regtest'])
    old = e['retained_regtest']
    same(old['engine_fix']['binary_sha256'], ENGINE, 'Retained recovery engine differs')
    candidate, prior = e['candidate_build'], e['prior_build']
    manifest = read(BUNDLE, 'source-manifest.json')
    repositories = candidate.get('repositories')
    require(type(repositories) is dict and set(repositories) == set(manifest), 'Candidate source pins missing')
    for name, spec in manifest.items():
        row = repositories[name]
        require(type(row) is dict and set(row) == {'commit','tree','branch','tag_object'}, 'Source receipt fields differ')
        require(all(type(row[k]) is str and re.fullmatch('[0-9a-f]{40}', row[k]) for k in ('commit','tag_object')),
                'Invalid checkpoint object')
        same(row['tree'], spec['before_tree'], 'Candidate source tree differs: '+name)
        same(row['branch'], spec['branch'], 'Candidate branch differs: '+name)
    images = candidate.get('images')
    require(type(images) is dict and set(images) == {'node','ui'} and
            all(type(v) is str and re.fullmatch('sha256:[0-9a-f]{64}',v) for v in images.values()), 'Image IDs missing')
    same(images['ui'], old['retained']['original_evidence']['images']['ui'], 'Retained UI image differs')
    common = dict(schema=1, checkpoint=BASE_TAG, repositories=repositories, package_id='xbt-cln',
        architecture='x86_64', source_export_sha256=PRIOR_EXPORT, engine_sha256=ENGINE,
        images=images, image_binding=image_binding(images), startos_installation_tested=False,
        startos_backup_restore_tested=False, swaps_active=False, legacy_wallet_migration=False)
    overlay = read(BUNDLE, 'tested-overlay.json')
    require(type(prior.get('images')) is dict and set(prior['images']) == {'node','ui','fixture'} and
            all(prior['images'][key] == images[key] for key in images) and
            type(prior['images']['fixture']) is str and re.fullmatch('sha256:[0-9a-f]{64}',prior['images']['fixture']),
            'Prior fixture image proof differs')
    for key in ('packed_node_files_verified','packed_ui_files_verified'):
        require(type(prior.get(key)) is int and prior[key] > 0, 'Prior packed-file verification missing')
    for receipt, fixed in [(prior, dict(common, milestone='0090a', version='#privkeyio:26.6.9:0',
            installer_sha256=PRIOR_INSTALLER, funded_node_ui=node_ui.expected(),
            scope='fresh-wallet-startos-candidate', images=prior['images'],
            retained_recovery_export_sha256=PRIOR_EXPORT,
            packed_node_files_verified=prior['packed_node_files_verified'],
            packed_ui_files_verified=prior['packed_ui_files_verified'],
            documentation_sha256=read(BUNDLE,'prior-documentation-hashes.json'))),
        (candidate, dict(common, milestone='0090b', version='#privkeyio:26.6.9:1', installer_sha256=INSTALLER,
            source_overlay=overlay, source_overlay_sha256=cp.digest(BUNDLE/'tested-overlay.patch'),
            retained_0090a_installer_sha256=PRIOR_INSTALLER, retained_funded_node_ui=node_ui.expected(),
            funded_fixture_rerun=False))]:
        require(set(receipt) == set(fixed)|{'startos_actions_sha256'}, 'Build receipt fields differ')
        for key, value in fixed.items(): same(receipt[key], value, 'Build receipt differs: '+key)
        require(type(receipt['startos_actions_sha256']) is str and
                re.fullmatch('[0-9a-f]{64}', receipt['startos_actions_sha256']), 'Compiled action hash missing')


def collect(directory, prior_export):
    package = cp.ordinary_path(directory, 'xbt-cln_x86_64.s9pk')
    require(package.is_file() and cp.digest(package) == INSTALLER, 'Exact accepted 0090b installer required: '+str(package))
    require(prior_export.is_file() and not prior_export.is_symlink() and cp.digest(prior_export) == PRIOR_EXPORT,
            'Exact retained 0089 export required: '+str(prior_export))
    with zipfile.ZipFile(prior_export) as archive:
        prefix='0089-privkeyio-recovery-checkpoint/'
        data=archive.read(prefix+'runtime-evidence.json')
        retained=json.loads(data)
        receipt=json.loads(archive.read(prefix+'export-receipt.json'))
        same(json.loads(archive.read(prefix+'source-manifest.json')),
             read(BUNDLE,'retained-0089-source-manifest.json'), 'Retained source manifest differs')
        require(receipt['tag'] == BASE_TAG and receipt['runtime_evidence_sha256'] == hashlib.sha256(data).hexdigest(),
                'Retained export receipt differs')
    same(read(directory, 'source-overlay.json'), read(BUNDLE,'tested-overlay.json'), 'Output source overlay differs')
    require(cp.digest(cp.ordinary_path(directory,'source-overlay.patch')) == cp.digest(BUNDLE/'tested-overlay.patch'),
            'Output source patch differs')
    require(cp.digest(cp.ordinary_path(directory,'probe-node.py')) == cp.digest(BUNDLE/'probe-node.py'),
            'Output probe differs')
    result=dict(schema=1, milestone='0091', candidate_build=read(directory,'build-receipt.json'),
                prior_build=read(directory,'prior-build-receipt.json'), retained_regtest=retained)
    validate(result)
    return result
