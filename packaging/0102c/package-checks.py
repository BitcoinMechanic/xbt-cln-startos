"""Validate the StartOS input/output transformation and embedded dependency files."""
import json

ICON_URL='https://raw.githubusercontent.com/Start9Labs/bitcoin-core-startos/feec0b1dae42961a257948fe39b40caf8672fce1/dep-icon.svg'
ICON_SHA256='86cdf6d03ddd38ca949e8d8e3f34bbc87abed12baf48bf090ce9e5b2339b3542'

def need(ok,why):
    if not ok:raise RuntimeError(why)

def same(a,b,why):need(json.dumps(a,sort_keys=True)==json.dumps(b,sort_keys=True),why)

def images(manifest,asset,sources=None):
    expected={'controller'} if asset=='controller' else {'lightning','ui'}
    need(set(manifest['images'])==expected,'Image set differs: '+asset)
    need(manifest['hardwareRequirements']['arch']==['x86_64'],'Package architecture differs: '+asset)
    for name,row in manifest['images'].items():
        label=asset+'/'+name
        same(row.get('source'),'packed' if sources is None else sources[name],'Image source differs: '+label)
        need(row.get('arch')==['x86_64'],'Image architecture differs: '+label)
        need(row.get('emulateMissingAs') is None and row.get('emulateMissing',False) is False,
             'Image emulation must be disabled: '+label)
        need(row.get('nvidiaContainer',False) is False,'Unexpected NVIDIA container: '+label)

def packed_manifest(packed,original,asset):
    for field in ('id','version','osVersion','sdkVersion','canMigrateTo','canMigrateFrom','volumes'):
        same(packed.get(field),original.get(field),'Packed manifest differs: '+field)
    images(packed,asset)
    need(set(packed['dependencies'])==set(original['dependencies']),'Packed dependency set differs')
    for name,expected in original['dependencies'].items():
        actual=dict(packed['dependencies'][name]);wanted=dict(expected)
        # pack.rs removes MetadataSrc and writes dependencies/<id>/metadata.json
        # and icon.svg. Neither dependency requirements nor descriptions change.
        need(actual.pop('metadata',None) is None,'Dependency metadata was not embedded: '+name)
        wanted.pop('metadata',None)
        # Newer CLI serializers explicitly emit the optional version range as
        # null; SDK 2.0.9 omits it. A non-null range must still match exactly.
        actual.setdefault('versionRange',None);wanted.setdefault('versionRange',None)
        same(actual,wanted,'Packed dependency contract differs: '+name)

def dependency_files(original,metadata,icon_sha256):
    expected=original['metadata']
    need(set(expected)=={'title','icon'} and expected['icon']==ICON_URL,'Dependency source metadata changed')
    same(metadata,{'title':expected['title']},'Packed dependency title differs')
    need(icon_sha256==ICON_SHA256,'Packed dependency icon differs from pinned source')
