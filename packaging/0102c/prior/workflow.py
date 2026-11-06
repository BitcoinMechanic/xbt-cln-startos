#!/usr/bin/env python3
"""Checkpoint verified migration sources: VM export, tower push, VM sync."""
import argparse
import datetime
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import uuid
import zipfile

import common as cp
import runtime_evidence as runtime

BUNDLE=Path(__file__).resolve().parent
TAG=cp.TAG
TAGREF='refs/tags/'+TAG


def require(ok,message):
    if not ok:raise RuntimeError(message)


def root_path(value):
    path=Path(value).expanduser().absolute()
    require(not any(p.is_symlink() for p in (path,*path.parents)), 'Symlinked workspace refused: '+str(path))
    return path.resolve()


def verify_bundle():
    seen=set()
    for row in (BUNDLE/'SHA256SUMS').read_text().splitlines():
        sha,name=row.split('  ',1)
        require(not Path(name).is_absolute() and '..' not in Path(name).parts and name not in seen, 'Invalid checksum member')
        seen.add(name)
        path=cp.ordinary_path(BUNDLE,name)
        require(path.is_file() and cp.digest(path)==sha,'Bundle checksum differs: '+name)
    return json.loads((BUNDLE/'source-manifest.json').read_text())


def owned(repo,name):
    require(repo.is_dir() and cp.git(repo,'rev-parse','--show-toplevel')==str(repo),'Unexpected repository root: '+str(repo))
    allowed=('https://github.com/BitcoinMechanic/'+name+'.git',
             'https://github.com/BitcoinMechanic/'+name,'git@github.com:BitcoinMechanic/'+name+'.git',
             'git@github.com:BitcoinMechanic/'+name)
    require(cp.git(repo,'config','--get','remote.origin.url') in allowed,'Unexpected origin: '+name)
    overrides=cp.git(repo,'config','--get-all','remote.origin.pushurl',check=False).splitlines()
    require(all(v in allowed for v in overrides),'Unexpected push destination: '+name)
    require(len(cp.git(repo,'remote','get-url','--push','--all','origin').splitlines())==1,
            'Multiple push destinations refused: '+name)


def ensure_base(repo,spec,*,fetch=False):
    # Resolve actual tower-created checkpoints, then verify their complete
    # known ancestry and exact source trees without inventing commit IDs.
    chain=spec['checkpoint_chain']
    require(chain[-1]['tag']==spec['base_tag'] and chain[-1]['tree']==spec['before_tree'],
            'Checkpoint manifest differs: '+repo.name)
    if fetch:
        refs=['refs/tags/'+item['tag'] for item in chain]
        cp.git(repo,'fetch','--no-tags','origin',*(ref+':'+ref for ref in refs))
    parent=spec['base_anchor']; checkpoints={}
    for item in chain:
        ref='refs/tags/'+item['tag']
        require(cp.git(repo,'cat-file','-t',ref)=='tag','Annotated checkpoint required: '+repo.name+'/'+item['tag'])
        commit=cp.git(repo,'rev-parse',ref+'^{commit}')
        require(cp.git(repo,'rev-parse',commit+'^{tree}')==item['tree'],'Checkpoint tree differs: '+repo.name+'/'+item['tag'])
        if item['new_commit']:
            require(cp.git(repo,'show','-s','--format=%P',commit)==parent,'Checkpoint parent differs: '+repo.name+'/'+item['tag'])
        else:
            require(commit==parent,'Unchanged checkpoint commit differs: '+repo.name+'/'+item['tag'])
        checkpoints[item['tag']]=commit
        parent=commit
    base=parent
    require('base_commit' not in spec or spec['base_commit']==base,'Base checkpoint changed during workflow: '+repo.name)
    tag_object=cp.git(repo,'rev-parse',ref)
    require('base_tag_object' not in spec or spec['base_tag_object']==tag_object,
            'Base tag changed during workflow: '+repo.name)
    spec['base_commit']=base
    spec['base_tag_object']=tag_object
    spec['checkpoint_commits']=checkpoints


def valid_commit(repo,spec,commit):
    ensure_base(repo,spec)
    require(cp.git(repo,'rev-parse',spec['base_commit']+'^{tree}')==spec['before_tree'],'Base tree differs: '+repo.name)
    if commit==spec['base_commit']:return
    require(spec['tree']!=spec['before_tree']
            and cp.git(repo,'rev-parse',commit+'^{tree}')==spec['tree']
            and cp.git(repo,'rev-list','--parents','-n','1',commit).split()==[commit,spec['base_commit']],
            'Unexpected commit; work retained: '+repo.name)


def inspect(repo,name,spec,*,vm):
    owned(repo,name)
    branch=cp.git(repo,'branch','--show-current')
    require(branch==spec['branch'] if vm else branch=='','Unexpected '+('VM branch' if vm else 'tower worktree branch')+': '+name)
    head=cp.git(repo,'rev-parse','HEAD')
    valid_commit(repo,spec,head)
    require(not cp.git(repo,'diff','--cached','--name-only'),'Staged work retained: '+name)
    for path,pin in spec['pins'].items():
        require(cp.git(repo,'rev-parse','HEAD:'+path)==pin,'Submodule pin differs: '+name+'/'+path)
    present=[]
    for path in spec['files']:
        target=cp.ordinary_path(repo,path)
        require(not target.exists() or target.is_file(),'Source is not an ordinary file: '+str(target))
        if target.is_file():present.append(path)
    tree=cp.prospective_tree(repo,present)
    require(tree in (spec['before_tree'],spec['tree']),'Unexpected source changes retained: '+name)
    phase='after' if tree==spec['tree'] else 'before'
    if phase=='after':
        for path,sha in spec['files'].items():
            require(cp.digest(repo/path)==sha,'Source hash differs: '+name+'/'+path)
    cp.git(repo,'diff','--check')
    return head,phase


def vm_marker(root):
    for name in ('NOT-INSTALLABLE.txt','migration-workspace.json'):
        p=cp.ordinary_path(root,name)
        require(p.is_file(),'Expected isolated 0065 migration workspace: '+str(root))


def refs(repo):
    raw=cp.git(repo,'ls-remote','origin',TAGREF,TAGREF+'^{}')
    return {ref:sha for sha,ref in (line.split() for line in raw.splitlines())}


def local_tag(repo):
    return cp.git(repo,'rev-parse','--verify','--quiet',TAGREF,check=False)


def fetch_remote(repo,spec):
    ensure_base(repo,spec,fetch=True)
    cp.git(repo,'fetch','--no-tags','origin','refs/heads/'+spec['branch'])
    commit=cp.git(repo,'rev-parse','FETCH_HEAD')
    valid_commit(repo,spec,commit)
    tags=refs(repo)
    if tags:
        require(tags.get(TAGREF+'^{}')==commit
                and cp.git(repo,'rev-parse',commit+'^{tree}')==spec['tree'],
                'Remote checkpoint branch/tag differs: '+repo.name)
        require(not local_tag(repo) or local_tag(repo)==tags.get(TAGREF),
                'Different local checkpoint tag retained: '+repo.name)
        cp.git(repo,'fetch','--no-tags','origin',TAGREF+':'+TAGREF)
        require(cp.git(repo,'cat-file','-t',TAGREF)=='tag','Annotated checkpoint required: '+repo.name)
    return commit,tags


def json_once(path,value):
    text=json.dumps(value,indent=2)+'\n'
    require(not path.is_symlink(),'Symlinked checkpoint record refused: '+str(path))
    require(not path.exists() or path.read_text()==text,'Existing checkpoint record differs; retained: '+str(path))
    path.write_text(text)


def bind_runtime(evidence,spec,name):
    runtime.bind(evidence,spec,name)


def export_vm(root,manifest,args):
    vm_marker(root)
    evidence=runtime.collect(root_path(args.results_dir))
    observations={}
    for name,spec in manifest.items():
        head,phase=inspect(cp.ordinary_path(root,name),name,spec,vm=True)
        require(phase=='after','Exact tested 0100 source required: '+name)
        require(head==spec['base_commit'],'Export from the tested pre-commit workspace, or reuse the existing export: '+name)
        observations[name]=dict(head=head,tree=spec['tree'],branch=spec['branch'],
                                base_commit=spec['base_commit'],base_tag_object=spec['base_tag_object'])
    for name in manifest:bind_runtime(evidence,manifest[name],name)
    backup=cp.ordinary_path(root,'checkpoints/'+TAG)
    backup.mkdir(parents=True,exist_ok=True,mode=0o700)
    with tempfile.TemporaryDirectory(prefix='actions-export-') as tmp:
        stage=Path(tmp)/BUNDLE.name;stage.mkdir()
        included=[line.split('  ',1)[1] for line in (BUNDLE/'SHA256SUMS').read_text().splitlines()]
        for filename in (*included,'SHA256SUMS'):
            if filename!='export-receipt.json':
                (stage/filename).parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(BUNDLE/filename,stage/filename)
        for name,spec in manifest.items():
            if spec['tree']==spec['before_tree']:continue
            repo=root/name
            with tempfile.TemporaryDirectory(prefix='actions-export-index-') as idx:
                env=dict(os.environ,GIT_INDEX_FILE=idx+'/index')
                cp.git(repo,'read-tree','HEAD',env=env)
                cp.git(repo,'add','-u','--','.',env=env)
                cp.git(repo,'add','--',*spec['files'],env=env)
                require(cp.git(repo,'write-tree',env=env)==spec['tree'],'Source changed during export: '+name)
                patch=subprocess.check_output(['git','-C',str(repo),'diff','--cached','--binary','--full-index',spec['base_commit']],env=env)
                (stage/(name+'.patch')).write_bytes(patch)
        json_once(stage/'runtime-evidence.json',evidence)
        json_once(stage/'export-receipt.json',dict(kind='verified-migration-source-export',
                  tag=TAG,repositories=observations,runtime_evidence_sha256=cp.digest(stage/'runtime-evidence.json')))
        (stage/'SHA256SUMS').write_text(''.join(cp.digest(p)+'  '+str(p.relative_to(stage))+'\n' for p in sorted(stage.rglob('*'))
                                               if p.is_file() and p!=stage/'SHA256SUMS'))
        exported=cp.ordinary_path(backup,'source-export.zip')
        members={stage.name+'/'+str(p.relative_to(stage)):p.read_bytes() for p in stage.rglob('*') if p.is_file()}
        if exported.exists():
            with zipfile.ZipFile(exported) as z:
                require(len(z.namelist())==len(members) and set(z.namelist())==set(members)
                        and all(z.read(k)==v for k,v in members.items()),'Existing source export differs; retained: '+str(exported))
        else:
            with tempfile.NamedTemporaryFile(dir=backup,suffix='.zip',delete=False) as out:temp=Path(out.name)
            try:
                with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED) as z:
                    for name,data in sorted(members.items()):z.writestr(name,data)
                temp.replace(exported)
            finally:temp.unlink(missing_ok=True)
    print('EXPORT READY: '+str(exported))
    print('SHA256: '+cp.digest(exported))
    print('Tested SDK action sources and verified 0100 funded evidence exported. Channels remain untouched. Indexes, refs and stashes preserved; no build or live-node action.')


def tower(root,manifest,args):
    receipt=json.loads((BUNDLE/'export-receipt.json').read_text())
    require(receipt.get('kind')=='verified-migration-source-export' and receipt.get('tag')==TAG,
            'Run the tower step from the VM-exported archive')
    require(cp.digest(BUNDLE/'runtime-evidence.json')==receipt['runtime_evidence_sha256'],'Exported runtime evidence differs')
    evidence=json.loads((BUNDLE/'runtime-evidence.json').read_text())
    runtime.validate(evidence)
    require(set(receipt['repositories'])==set(manifest),'Export repository set differs')
    cache=root_path(args.cache_root)
    plans=[]
    for name,spec in manifest.items():
        require(receipt['repositories'][name]['tree']==spec['tree'],'Export receipt tree differs: '+name)
        original=cp.ordinary_path(cache,name)
        require(original.is_dir(),'Existing tower clone missing: '+str(original)+'; use --cache-root with its existing parent')
        owned(original,name)
        remote,tags=fetch_remote(original,spec)
        bind_runtime(evidence,spec,name)
        require(receipt['repositories'][name]==dict(head=spec['base_commit'],tree=spec['tree'],branch=spec['branch'],
                base_commit=spec['base_commit'],base_tag_object=spec['base_tag_object']),
                'VM and tower base checkpoints differ: '+name)
        path=cp.ordinary_path(root,name)
        if path.exists():
            head,phase=inspect(path,name,spec,vm=False)
            require(cp.git(path,'rev-parse','--path-format=absolute','--git-common-dir')
                    ==cp.git(original,'rev-parse','--path-format=absolute','--git-common-dir'),
                    'Existing tower worktree belongs to another clone: '+name)
            require(remote in (spec['base_commit'],head),'Remote branch advanced; work retained: '+name)
            if phase=='before':
                for filename in spec['files']:cp.ordinary_path(path,filename)
                cp.git(path,'apply','--check',str(BUNDLE/(name+'.patch')))
        else:head,phase=remote,'new'
        if local_tag(original):
            require(cp.git(original,'cat-file','-t',TAGREF)=='tag'
                    and cp.git(original,'rev-parse',TAGREF+'^{commit}')==head
                    and cp.git(original,'rev-parse',TAGREF+'^{tree}')==spec['tree'],
                    'Existing local checkpoint tag differs: '+name)
        cp.git(original,'var','GIT_AUTHOR_IDENT');cp.git(original,'var','GIT_COMMITTER_IDENT')
        plans.append((name,spec,original,path,remote))
    # Reuse object databases; leave every existing checkout and its HEAD/index alone.
    root.mkdir(parents=True,exist_ok=True)
    for name,spec,original,path,remote in plans:
        if not path.exists():cp.git(original,'worktree','add','--detach',str(path),remote)
    for name,spec,original,path,remote in plans:
        head,phase=inspect(path,name,spec,vm=False)
        if phase=='before':cp.git(path,'apply','--check',str(BUNDLE/(name+'.patch')))
    for name,spec,original,path,remote in plans:
        head,phase=inspect(path,name,spec,vm=False)
        if phase=='before':cp.git(path,'apply',str(BUNDLE/(name+'.patch')))
        require(inspect(path,name,spec,vm=False)[1]=='after','Applied source differs: '+name)
    backup=cp.ordinary_path(root,'checkpoints/'+TAG);backup.mkdir(parents=True,exist_ok=True,mode=0o700)
    for filename in ('source-manifest.json','runtime-evidence.json','operator-report.json'):
        cp.preserve(BUNDLE/filename,cp.ordinary_path(backup,filename))
    for name,spec,original,path,remote in plans:
        head,phase=inspect(path,name,spec,vm=False)
        if cp.git(path,'rev-parse','HEAD^{tree}')!=spec['tree']:
            cp.git(path,'add','--',*spec['files'])
            require(cp.git(path,'write-tree')==spec['tree'],'Unexpected staged tree retained: '+name)
            cp.git(path,'commit','--file',str(BUNDLE/'commit-message.txt'))
        head=cp.git(path,'rev-parse','HEAD');valid_commit(path,spec,head)
        if not local_tag(path):cp.git(path,'tag','-a',TAG,'--file',str(BUNDLE/'commit-message.txt'))
        require(cp.git(path,'rev-parse',TAGREF+'^{commit}')==head,'Local tag differs: '+name)
    # Check every remote again before any push; never force a branch or tag.
    records={}
    for name,spec,original,path,_ in plans:
        head=cp.git(path,'rev-parse','HEAD');remote,tags=fetch_remote(path,spec)
        require(remote in (spec['base_commit'],head),'GitHub advanced; no force-push: '+name)
        require(not tags or tags[TAGREF]==local_tag(path),'Remote tag changed: '+name)
        records[name]=dict(commit=head,tree=spec['tree'],branch=spec['branch'],tag_object=local_tag(path))
    json_once(backup/'checkpoint.json',dict(tag=TAG,repositories=records))
    for name,spec,_,path,_ in plans:
        cp.git(path,'push','--atomic','origin',records[name]['commit']+':refs/heads/'+spec['branch'],TAGREF)
        print('PUSHED: '+name+' '+spec['branch']+' '+records[name]['commit'],flush=True)
    print('TOWER PUSH COMPLETE: four source commits and all four migration checkpoint tags are on GitHub.')


def sync_vm(root,manifest,args):
    vm_marker(root)
    plans=[]
    for name,spec in manifest.items():
        repo=cp.ordinary_path(root,name)
        head,phase=inspect(repo,name,spec,vm=True)
        commit,tags=fetch_remote(repo,spec)
        require(tags.get(TAGREF+'^{}')==commit and cp.git(repo,'rev-parse',commit+'^{tree}')==spec['tree'],
                'Expected checkpoint is not on GitHub yet: '+name)
        require(head in (spec['base_commit'],commit),'Divergent VM commit retained: '+name)
        plans.append((name,spec,repo,head,commit))
    backup=cp.ordinary_path(root,'checkpoints/'+TAG);backup.mkdir(parents=True,exist_ok=True,mode=0o700)
    for name,spec,repo,head,commit in plans:
        # Recheck source/index after remote preflight. A clean base also permits
        # resuming after a prior run stashed the delta but had not yet merged it.
        inspect(repo,name,spec,vm=True)
        old=cp.git(repo,'rev-parse','--verify','--quiet','refs/stash',check=False)
        cp.git(repo,'stash','push','--include-untracked','--message',TAG+' migration before GitHub sync')
        new=cp.git(repo,'rev-parse','--verify','--quiet','refs/stash',check=False)
        stash=new if new!=old else None
        stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
        json_once(backup/('sync-'+name+'-'+stamp+'-'+uuid.uuid4().hex[:6]+'.json'),
                  dict(before=head,target=commit,retained_stash=stash))
        cp.git(repo,'merge','--ff-only',commit)
        require(inspect(repo,name,spec,vm=True)==(commit,'after'),'Synced source differs: '+name)
        print('SYNCED: '+name+' '+commit+('; retained stash '+stash if stash else '; no new stash needed'),flush=True)
    print('VM SYNC COMPLETE: migration checkpoint checked out; stashes retained. Do not pop them onto the already-applied checkpoint.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=('export-vm','tower','sync-vm'))
    parser.add_argument('root',nargs='?')
    parser.add_argument('--cache-root',default='~/code/cln-blake')
    parser.add_argument('--results-dir',default='/tmp/privkeyio-0100-results.l8yon5ti')
    args=parser.parse_args()
    default='~/tmp/cln-privkeyio-actions-checkpoint' if args.mode=='tower' else '~/code/cln-blake/privkeyio-migration'
    root=root_path(args.root or default)
    {'export-vm':export_vm,'tower':tower,'sync-vm':sync_vm}[args.mode](root,verify_bundle(),args)


if __name__=='__main__':
    try:main()
    except Exception as error:raise SystemExit('0101 stopped: '+str(error)) from None
