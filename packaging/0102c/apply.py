#!/usr/bin/env python3
"""Apply 0102 over exact 0101 to the complete annotated 0101 migration checkpoint."""
import argparse
import json
from pathlib import Path
import common as cp

BUNDLE = Path(__file__).resolve().parent
TAG = 'privkeyio-startos-actions-20261014'


def need(ok, message):
    if not ok: raise RuntimeError(message)


def inspect(root, name, spec):
    repo = cp.ordinary_path(root,name)
    need(repo.is_dir() and cp.git(repo,'rev-parse','--show-toplevel') == str(repo), 'Repository path differs: '+name)
    need(cp.git(repo,'branch','--show-current') == spec['branch'], 'Branch differs: '+name)
    origin = cp.git(repo,'config','--get','remote.origin.url').removesuffix('.git')
    need(origin in ('https://github.com/BitcoinMechanic/'+name,'git@github.com:BitcoinMechanic/'+name), 'Origin differs: '+name)
    parent = spec['base_anchor']
    for point in spec['checkpoint_chain']:
        ref = 'refs/tags/'+point['tag']
        need(cp.git(repo,'cat-file','-t',ref) == 'tag', 'Annotated checkpoint required: '+point['tag'])
        head = cp.git(repo,'rev-parse',ref+'^{commit}')
        need(cp.git(repo,'rev-parse',head+'^{tree}') == point['tree'], 'Checkpoint tree differs: '+name+'/'+point['tag'])
        if point['new_commit']:
            need(cp.git(repo,'show','-s','--format=%P',head) == parent, 'Checkpoint parent differs: '+name)
        else:
            need(head == parent, 'Unchanged checkpoint commit differs: '+name)
        parent = head
    need(spec['checkpoint_chain'][-1]['tag'] == TAG and spec['checkpoint_chain'][-1]['tree'] == spec['before_tree'],
         'Manifest base differs: '+name)
    need(cp.git(repo,'rev-parse','HEAD') == head, 'HEAD is not the synced 0101 checkpoint: '+name)
    need(not cp.git(repo,'diff','--cached','--name-only'), 'Staged work retained: '+name)
    for path,pin in spec['pins'].items():
        need(cp.git(repo,'ls-tree','HEAD','--',path).split()[:3] == ['160000','commit',pin], 'Gitlink differs: '+name+'/'+path)
    before = after = True
    present = []
    for path,hashes in spec['files'].items():
        target = cp.ordinary_path(repo,path)
        need(not target.exists() or target.is_file(), 'Non-file source path retained: '+path)
        actual = cp.digest(target) if target.is_file() else None
        before = before and actual == hashes['before']
        after = after and actual == hashes['after']
        if target.is_file(): present.append(path)
    need(before or after, 'Source differs from checkpoint, 0102; work retained: '+name)
    tree = cp.prospective_tree(repo,present)
    need(tree == (spec['tree'] if after else spec['before_tree']), 'Other source/submodule changes retained: '+name)
    cp.git(repo,'diff','--check',spec['before_tree'],tree)
    return 'after' if after else 'before'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root',type=Path); parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    raw = args.root.expanduser().absolute()
    need(not any(p.is_symlink() for p in (raw,*raw.parents)), 'Symlinked workspace refused')
    root = raw.resolve()
    for name in ('NOT-INSTALLABLE.txt','migration-workspace.json'):
        need(cp.ordinary_path(root,name).is_file(), 'Use the isolated migration workspace')
    for line in (BUNDLE/'SHA256SUMS').read_text().splitlines():
        digest,name = line.split('  ',1)
        need(cp.digest(cp.ordinary_path(BUNDLE,name)) == digest, 'Bundle checksum differs: '+name)
    manifest = json.loads((BUNDLE/'source-manifest.json').read_text())
    plans = {name:inspect(root,name,spec) for name,spec in manifest.items()}
    if args.check:
        need(all(p == 'after' for p in plans.values()), '0102 is not fully applied; no files changed')
    else:
        for name,phase in plans.items():
            if phase != 'after': cp.git(root/name,'apply','--check',str(BUNDLE/(name+'.patch')))
        for name,phase in plans.items():
            if phase != 'after': cp.git(root/name,'apply',str(BUNDLE/(name+'.patch')))
        for name,spec in manifest.items():
            need(inspect(root,name,spec) == 'after', 'Post-apply verification failed: '+name)
    print('0102 verified; exact 0101 checkpoint, branches, source trees and gitlinks. Indexes, refs and stashes retained.')


if __name__ == '__main__':
    try: main()
    except Exception as error: raise SystemExit('0102 stopped: '+str(error)) from None
