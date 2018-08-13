import concurrent.futures
import logging
import os
import random
import re
import time
import urllib.error
import urllib.request

from .config import Config

with open(Config.UA_FILE) as f:
    _ua = list(u.strip() for u in f.readlines())


def rand_ua():
    return random.choice(_ua)


def save_file(localpath, data):
    dirname = os.path.dirname(localpath)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(localpath, 'wb') as f:
        f.write(data)


def load_file(localpath):
    if os.path.exists(localpath):
        with open(localpath, 'rb') as f:
            return f.read()
    else:
        return None


def get(netpath, retry=3):
    for _ in range(retry):
        try:
            req = urllib.request.Request(
                netpath, headers={'User-Agent': rand_ua()})
            with urllib.request.urlopen(req, timeout=Config.TIMEOUT) as conn:
                return conn.read()
        except urllib.error.HTTPError as err:
            logging.debug(f'get {netpath} err: {err}')
    return None


def download(localpath, netpath):
    logging.debug('download ' + netpath)
    data = get(netpath)
    if data:
        save_file(localpath, data)
    return data


def load_or_get(basepair, path, cover=False):
    localbase, netbase = basepair
    localpath = os.path.join(localbase, path)
    netpath = f"{netbase.rstrip('/')}/{path.lstrip('/')}"

    ret = None
    if cover or not os.path.exists(localpath):
        ret = download(localpath, netpath)

    return ret or load_file(localpath)


def isdirlist(url):
    keywords = [
        'To Parent Directory',
        'Index of /',
        'Directory Listing For /',
        '[转到父目录]',
        'objects/',
    ]
    data = get(url)
    if data:
        data = data.decode('utf-8', 'replace')
        for key in keywords:
            if key in data:
                return True
    return False


def dirlist_spider(basepair):
    dirlist_ptn = re.compile(br'<td>\s*<a href="([^"]+)', re.M | re.I)
    localbase, netbase = basepair
    localbase = localbase.rstrip('/')
    netbase = netbase.rstrip('/')
    with concurrent.futures.ThreadPoolExecutor(Config.THREADS) as executor:
        tasks = []

        def recursive(path='/'):
            localpath = os.path.join(localbase, path.strip('/'))
            netpath = f"{netbase}/{path.lstrip('/')}"
            if path.endswith('/'):
                logging.debug('detect path: ' + path)
                os.makedirs(localpath, exist_ok=True)
                page = get(netpath)
                if page:
                    for _f in dirlist_ptn.findall(page):
                        _f = _f.decode('utf-8', 'replace')
                        if '../' == _f or _f.startswith('/'):
                            continue
                        recursive(f'{path}{_f}')
            else:
                logging.debug('detect file: ' + path)
                tasks.append(executor.submit(download, localpath, netpath))
                time.sleep(0.2)

        recursive()
        concurrent.futures.wait(tasks)
