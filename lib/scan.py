import os
import shutil
from urllib import parse

from . import log
from .config import Config
from .git import clone, get_cache, init, update_files, valid_repo
from .net import dirlist_download, isdirlist


class GitScanner(object):
    def __init__(self, url):
        self.endpoint = url.rstrip('/')
        distname = parse.urlparse(url).netloc.replace(':', '_')
        self.cwd = os.path.join(Config.dist, distname)
        os.makedirs(self.cwd, exist_ok=True)
        localgit = os.path.join(self.cwd, '.git')
        netgit = self.endpoint + '/.git'
        self.gitpair = (localgit, netgit)

    def scan(self):
        log.info('plan A: try to clone directly')
        with log.RunningBar('plan A'):
            result = self.plan_a()
        if not result:
            log.info('plan B: try to clone with directory listing')
            with log.RunningBar('plan B'):
                result = self.plan_b()
        if not result:
            log.info('plan C: try to clone with cache')
            with log.RunningBar('plan C'):
                result = self.plan_c()

        if result:
            log.success('clone success => ' + self.cwd)
        else:
            log.failure('clone fail')

    def plan_a(self):
        localgit, _ = self.gitpair
        if os.path.exists(localgit):
            log.info('local git already exists')
            if valid_repo(self.cwd):
                log.success('local git valid')
                return True
            log.warning("local git invalid, remove '.git'")
            shutil.rmtree(localgit, ignore_errors=True)
        return clone(self.cwd, self.endpoint)

    def plan_b(self):
        localgit, netgit = self.gitpair
        if not isdirlist(netgit):
            log.failure(f"skip: {netgit} don't support directory listing")
            return False
        try:
            if not os.path.exists(localgit):
                init(self.cwd)
            dirlist_download(self.gitpair)
            update_files(self.gitpair)
            if not valid_repo(self.cwd):
                log.warning('plan B done, but some files are missing')
            return True
        except Exception as e:
            log.debug(f'unknown err: {e}')
            return False

    def plan_c(self):
        localgit, _ = self.gitpair
        if not os.path.exists(localgit):
            init(self.cwd)
        get_cache(self.gitpair)
        if not valid_repo(self.cwd):
            log.warning('plan C done, but some files are missing')
        return True
