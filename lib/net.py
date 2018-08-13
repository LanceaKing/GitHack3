import logging
import os
import random
import re
import urllib
from concurrent.futures import ThreadPoolExecutor, wait
from urllib import request

from .config import Config

with open(Config.ua_file) as f:
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
    with open(localpath, 'rb') as f:
        return f.read()


def get(netpath, retry=3):
    for _ in range(retry):
        try:
            req = request.Request(netpath, headers={'User-Agent': rand_ua()})
            data = request.urlopen(req).read()
            if data:
                return data
        except Exception as e:
            logging.debug('Request Exception: ' + str(e))
    return None


def download(localpath, netpath):
    data = get(netpath)
    if not data:
        return None

    save_file(localpath, data)
    return data


def load_or_get(basepair, path, cover=False):
    localbase, netbase = basepair
    localpath = os.path.join(localbase, path)
    netpath = f"{netbase.rstrip('/')}/{path.lstrip('/')}"
    if cover or not os.path.exists(localpath):
        return download(localpath, netpath)
    else:
        return load_file(localpath)

    if os.path.exists(localpath):
        return load_file(localpath)
    else:
        return None


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
        for key in keywords:
            if key in data:
                return True
    return False


dirlist_ptn = re.compile(r'<td>\s*<a href="(.+?)"', re.M | re.I)


def dirlist_download(basepair):
    dirlist_ptn = re.compile(r'<td>\s*<a href="(.+?)"', re.M | re.I)
    executor = ThreadPoolExecutor(5)
    localbase, netbase = basepair
    localbase = localbase.rstrip('/')
    netbase = netbase.rstrip('/')
    tasks = []

    def recursive(path='/'):
        localpath = os.path.join(localbase, path.strip('/'))
        netpath = f"{netbase}/{path.lstrip('/')}"
        if path.endswith('/'):
            os.makedirs(localpath, exist_ok=True)
            page = get(netpath)
            files = dirlist_ptn.findall(page)
            for f in files:
                if "../" == f or f.startswith('/'):
                    continue
                recursive(f'{path}{f}')
        else:
            tasks.append(executor.submit(download, (localpath, netpath)))

    recursive()
    wait(tasks)
