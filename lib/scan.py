import os
import urllib.parse

from . import log
from .config import Config
from .git import clone, fake_clone, init, validate_repo
from .net import dirlist_spider, isdirlist, load_or_get


class GitScanner(object):
    def __init__(self, url):
        self.endpoint = url.rstrip('/')
        distname = urllib.parse.urlparse(url).netloc.replace(':', '_')
        self.cwd = os.path.join(Config.DIST, distname)
        os.makedirs(self.cwd, exist_ok=True)
        localgit = os.path.join(self.cwd, '.git')
        netgit = self.endpoint + '/.git'
        self.gitpair = (localgit, netgit)

    def scan(self):
        log.info('plan A: try direct clone')
        with log.RunningBar('plan A'):
            result = self.plan_a()
        if not result:
            log.info('plan B: try directory listing')
            with log.RunningBar('plan B'):
                result = self.plan_b()
        if not result:
            log.info('plan C: try fake clone')
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
            if validate_repo(self.cwd):
                log.success('local git valid')
                return True
            log.warning("local git invalid")
        return clone(self.cwd, self.endpoint)

    def plan_b(self):
        localgit, netgit = self.gitpair
        if not isdirlist(netgit):
            log.failure(netgit + " don't support directory listing")
            return False
        try:
            if not os.path.exists(localgit):
                init(self.cwd)

            dirlist_spider(self.gitpair)
            load_or_get(self.gitpair, 'packed-refs', True)
            load_or_get(self.gitpair, 'config', True)
            load_or_get(self.gitpair, 'HEAD', True)

            if not validate_repo(self.cwd):
                log.warning('plan B done, but some files are missing')
            return True
        except Exception as err:
            log.debug('unknown err: ' + str(err))
            return False

    def plan_c(self):
        localgit, _ = self.gitpair
        if not os.path.exists(localgit):
            init(self.cwd)

        fake_clone(self.gitpair)

        if not validate_repo(self.cwd):
            log.warning('plan C done, but some files are missing')
        return True
