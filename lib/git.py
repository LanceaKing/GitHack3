import concurrent.futures
import os
import subprocess
import sys
import threading
import zlib

from . import log
from .config import Config
from .net import load_or_get, save_file
from .parser import (find_sha1, parse_blob, parse_commit, parse_index,
                     parse_tree)


def check_git():
    log.debug('check git')
    cmd = ['git', '--version']
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        log.critical(r.stderr)
        sys.exit(r.returncode)
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


def validate_repo(cwd):
    cmd = ['git', 'log']
    r = subprocess.run(cmd, cwd=cwd, capture_output=True)
    if r.returncode == 0:
        log.info('valid repository success')
        return True
    log.debug(f'git:{r.returncode},stderr={r.stderr}')
    log.warning('valid repository fail')
    return False


def fake_clone(gitpair):
    with concurrent.futures.ThreadPoolExecutor(Config.THREADS) as executor:
        sha1 = set()
        sha1_lock = threading.Lock()

        def _load(path, cover=False, hash_cap=False):
            data = load_or_get(gitpair, path, cover)
            if hash_cap:
                sha1_lock.acquire()
                h = find_sha1(data)
                log.debug(f'{path}: {h}')
                sha1.update(h)
                sha1_lock.release()
            return data

        tasks = []

        def _add_task(*args, **kwargs):
            future = executor.submit(_load, *args, **kwargs)
            tasks.append(future)
            return future

        future_head = _add_task('HEAD', cover=True)
        _add_task('config', cover=True)
        _add_task('description', cover=True)
        _add_task('info/exclude', cover=True)
        _add_task('refs/heads/master', hash_cap=True)
        _add_task('refs/remotes/origin/master', hash_cap=True)
        _add_task('refs/remotes/origin/HEAD', hash_cap=True)
        _add_task('refs/stash', hash_cap=True)
        _add_task('packed-refs', cover=True, hash_cap=True)
        _add_task('logs/HEAD', hash_cap=True)
        _add_task('logs/refs/heads/master', hash_cap=True)
        _add_task('logs/refs/remotes/origin/master', hash_cap=True)
        _add_task('logs/refs/remotes/origin/HEAD', hash_cap=True)
        _add_task('FETCH_HEAD', hash_cap=True)
        _add_task('ORIG_HEAD', hash_cap=True)
        _add_task('COMMIT_EDITMSG')
        _add_task('index')

        refs = future_head.result()
        if refs:
            headpath = refs.decode('utf-8', 'replace').split(':')[1].strip()
            _add_task(headpath, hash_cap=True)
            _add_task('logs/' + headpath, hash_cap=True)

        concurrent.futures.wait(tasks)

    hashes_walk(gitpair, sha1)

    index_extract(gitpair)


def hashes_walk(gitpair, hashes):
    hashpool = set(hashes)
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
        except Exception as err:
            log.error(err)
        usedhash.add(h)


def index_extract(gitpair):
    localgit, _ = gitpair
    indexpath = os.path.join(localgit, 'index')
    local = os.path.dirname(localgit)
    entrys = parse_index(indexpath)

    index = entrys.send(None)  #start

    def _restore_blob(entry):
        try:
            h = entry['sha1']
            n = entry['name']
            zdata = load_or_get(gitpair, f'objects/{h[:2]}/{h[2:]}')
            data = zlib.decompress(zdata)
            blob = parse_blob(data)
            save_file(os.path.join(local, n), blob['data'])
        except Exception as err:
            log.error(f'restore {n} failed: {err}')

    with concurrent.futures.ThreadPoolExecutor(Config.THREADS) as executor:
        tasks = {executor.submit(_restore_blob, e): e for e in entrys}
        for future in concurrent.futures.as_completed(tasks):
            e = tasks[future]
            h = e['sha1']
            n = e['name']
            log.info(f'restore blob: {h} => {n}')
