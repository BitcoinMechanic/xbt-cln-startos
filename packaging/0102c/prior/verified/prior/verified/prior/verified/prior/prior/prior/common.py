"""Shared Git operations; preserve real indexes during verification."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

TAG = 'privkeyio-startos-empty-20261012'
BUNDLE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def run(args, *, env=None, check=True):
    # Read-only Git checks must not refresh the caller's real staging index.
    command_env = dict(os.environ if env is None else env, GIT_OPTIONAL_LOCKS='0')
    result = subprocess.run(args, env=command_env, text=True, capture_output=True)
    if check and result.returncode:
        raise RuntimeError('Command failed: ' + ' '.join(map(str, args[:4])) + '\n' + result.stderr.strip())
    return result


def git(repo, *args, **kwargs):
    if args[0] in ('diff', 'apply') and 'env' not in kwargs:
        # Some Git diff paths refresh cached stat data even with optional locks
        # disabled. Compare using a copy, including any pre-existing staged work.
        index = Path(run(['git', '-C', str(repo), 'rev-parse', '--git-path', 'index']).stdout.strip())
        if not index.is_absolute():
            index = repo / index
        with tempfile.TemporaryDirectory(prefix='swap-read-index-') as tmp:
            copy = Path(tmp) / 'index'
            shutil.copy2(index, copy)
            env = dict(os.environ, GIT_INDEX_FILE=str(copy))
            return run(['git', '-C', str(repo), *args], env=env, **kwargs).stdout.strip()
    return run(['git', '-C', str(repo), *args], **kwargs).stdout.strip()


def ordinary_path(repo, name):
    path = repo / name
    for component in (path, *path.parents):
        if component.is_symlink():
            raise RuntimeError('Symlink refused: ' + str(component))
        if component == repo: break
    return path


def prospective_tree(repo, files):
    with tempfile.TemporaryDirectory(prefix='swap-checkpoint-index-') as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / 'index'))
        git(repo, 'read-tree', 'HEAD', env=env)
        git(repo, 'add', '-u', '--', '.', env=env)
        if files: git(repo, 'add', '--', *files, env=env)
        return git(repo, 'write-tree', env=env)


def preserve(source, target):
    expected = digest(source)
    if target.exists():
        if digest(target) != expected:
            raise RuntimeError('Existing backup differs; preserved: ' + str(target))
    else:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix='.checkpoint-', delete=False) as f:
            temp = Path(f.name)
            with source.open('rb') as source_file:
                shutil.copyfileobj(source_file, f, length=1024 * 1024)
        if digest(temp) != expected:
            raise RuntimeError('Backup copy failed verification: ' + str(temp))
        temp.replace(target)
    return expected

