import os
import subprocess
import sys
import zlib
from concurrent.futures import ThreadPoolExecutor, wait

from . import log
from .net import load_or_get, save_file
from .parser import parse_blob, parse_commit, parse_index, parse_tree


def checkgit():
    log.debug('check git')
    cmd = ['git', '--version']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        log.critical(r.stderr)
        sys.exit(1)
    log.success(r.stdout.decode('utf-8', 'replace').strip())


def init(cwd):
    cmd = ['git', 'init']
    r = subprocess.run(cmd, cwd=cwd, capture_output=True)
    if r.returncode != 0:
        log.debug(f'git:{r.returncode},stderr={r.stderr}')
        log.error('init fail')


def clone(cwd, url):
    cmd = ['git', 'clone', url, cwd]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode == 0:
        log.info('clone success')
        return True
    log.debug(f'git:{r.returncode},stderr={r.stderr}')
    log.failure('clone fail')
    return False


def valid_repo(cwd):
    cmd = ['git', 'reset']
    r = subprocess.run(cmd, cwd=cwd, capture_output=True)
    if r.returncode == 0:
        log.info('valid repository success')
        return True
    log.debug(f'git:{r.returncode},stderr={r.stderr}')
    log.warning('valid repository fail')
    return False


def update_files(gitpair):
    load_or_get(gitpair, 'packed-refs', True)
    load_or_get(gitpair, 'config', True)
    load_or_get(gitpair, 'HEAD', True)


def get_cache(gitpair):
    update_files(gitpair)
    load_or_get(gitpair, 'COMMIT_EDITMSG')
    load_or_get(gitpair, 'info/exclude')
    load_or_get(gitpair, 'FETCH_HEAD')
    load_or_get(gitpair, 'refs/heads/master')
    refs = load_or_get(gitpair, 'HEAD').split(b':')[1].strip()
    refs = refs.decode('utf-8', 'replace').strip()
    load_or_get(gitpair, 'index')
    load_or_get(gitpair, 'logs/HEAD', True)
    head_hash = load_or_get(gitpair, refs).decode('ascii').strip()
    load_or_get(gitpair, f'logs/{refs}')

    if head_hash:
        traversal_hash(gitpair, head_hash)

    stash_hash = load_or_get(gitpair, 'refs/stash')
    if stash_hash:
        traversal_hash(gitpair, stash_hash)

    index_extract(gitpair)


def traversal_hash(gitpair, seedhash):
    hashpool = set([seedhash])
    usedhash = set()
    while len(hashpool) > 0:
        h = hashpool.pop()
        if h in usedhash:
            continue
        zdata = load_or_get(gitpair, f'objects/{h[:2]}/{h[2:]}')
        try:
            data = zlib.decompress(zdata)
            if data.startswith(b'tree'):
                log.info('detect tree: ' + h)
                tree = parse_tree(data)
                hashpool.update(t['sha1'] for t in tree)
            elif data.startswith(b'commit'):
                log.info('detect commit: ' + h)
                commit = parse_commit(data)
                if commit['tree']:
                    hashpool.add(commit['tree'])
                if commit['parent']:
                    hashpool.add(commit['parent'])
            elif data.startswith(b'blob'):
                log.info('detect blob: ' + h)
                pass
            else:
                log.warning('unknown file')
        except Exception as e:
            log.error(str(e))
        usedhash.add(h)


def index_extract(gitpair):
    localgit, _ = gitpair
    indexpath = os.path.join(localgit, 'index')
    local = os.path.dirname(localgit)
    entrys = parse_index(indexpath)

    entrys.send(None)  #start

    def _save_blob(entry):
        try:
            h = entry['sha1']
            name = entry['name']
            log.info(f'extract {name}: {h}')

            zdata = load_or_get(gitpair, f'objects/{h[:2]}/{h[2:]}')
            data = zlib.decompress(zdata)
            blob = parse_blob(data)
            save_file(os.path.join(local, name), blob['data'])
        except Exception as e:
            log.error(f'extract {name} failed: {e}')

    executor = ThreadPoolExecutor(5)
    tasks = [executor.submit(_save_blob, e) for e in entrys]
    wait(tasks)
