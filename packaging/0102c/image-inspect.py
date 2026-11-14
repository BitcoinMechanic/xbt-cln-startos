"""Read-only in-image inventories. Called only by the host build runner."""
import hashlib,json,os,subprocess,sys
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def inventory(root):
    root=Path(root);result={}
    for p in sorted(root.rglob('*')):
        if p.is_symlink():result[str(p.relative_to(root))]=dict(link=os.readlink(p))
        elif p.is_file():result[str(p.relative_to(root))]=dict(sha256=sha(p),executable=bool(p.stat().st_mode&0o111))
    return result
mode=sys.argv[1]
if mode=='parent':
    s=json.loads(Path('/opt/swap0094/fixture-source.json').read_text())
    result=dict(source=s,files={k:sha(Path('/opt/swap0094')/k) for k in s['files']},
        controller={k:sha(Path('/opt/controller0094')/k) for k in s['controller_files']},
        engines={f'/opt/{a}/bin/lightningd':sha(Path('/opt')/a/'bin/lightningd') for a in ('btc','xbt')},
        rest={a:sha(Path('/opt')/a/'libexec/c-lightning/plugins/clnrest') for a in ('btc','xbt')},
        versions={a:subprocess.check_output([f'/opt/{a}/bin/lightningd','--version'],text=True).strip() for a in ('btc','xbt')},
        native={a:inventory(Path('/opt')/a) for a in ('btc','xbt')})
else:
    role='controller' if mode=='controller' else 'node'
    root=Path('/usr/local/libexec')/('swap-'+role);sys.path.insert(0,str(root))
    import package_verify
    result=dict(manifest=package_verify.verify(root,role),runtime=inventory(root))
    if role=='node':
        result['native']=inventory(Path('/opt')/mode)
        result['version']=subprocess.check_output([f'/opt/{mode}/bin/lightningd','--version'],text=True).strip()
        # Verify real executable and shared-library availability in this small
        # image before allowing a fixture built atop the larger parent image.
        for binary in [Path('/opt')/mode/'bin/lightning-cli',Path('/opt')/mode/'bin/lightningd',
                       *sorted((Path('/opt')/mode/'libexec/c-lightning').rglob('*'))]:
            if not binary.is_file() or binary.is_symlink():continue
            if binary.read_bytes()[:4]!=b'\x7fELF':continue
            check=subprocess.run(['ldd',str(binary)],capture_output=True,text=True)
            if 'not found' in check.stdout+check.stderr:raise ValueError('runtime_shared_library_missing')
        result['shared_libraries_available']=True
print(json.dumps(result,sort_keys=True))
