import sys
import json
from collections import defaultdict
import logging
from os import makedirs
from os.path import isdir, join

import config
import egginst
from enstaller import main as enstaller_main
from enstaller.main import egginst_install, egginst_remove
from plat import custom_plat
from utils import open_with_auth, get_installed_info, comparable_version, \
    cname_fn
from verlib import IrrationalVersionError
from indexed_repo.chain import Chain, Req
from indexed_repo import dist_naming
from indexed_repo.requirement import add_Reqs_to_spec

logger = logging.getLogger(__name__)


class Resources(object):

    def __init__(self, urls, verbose=False, prefix=None, platform=None):
        self.prefix = prefix or sys.prefix
        self.plat = platform or custom_plat

        self.verbose = verbose
        self.index = []
        self.chain = Chain(verbose=verbose)
        for url in urls:
            self.add_product(url)

        # Cache attributes
        self._installed_cnames = None
        self._status = None
        self._installed = None

    def clear_cache(self):
        self._installed_cnames = None
        self._status = None
        self._installed = None

    def add_product(self, url):
        url = url.rstrip('/') + '/'
        if self.verbose:
            print "Adding product:", url

        index_fn = '.index-%s.json' % self.plat
        if url.startswith('file://'):
            path = url[7:]
            fi = open(join(path, index_fn))
            index = json.load(fi)
            fi.close()
        elif url.startswith(('http://', 'https://')):
            fi = open_with_auth(url + index_fn)
            index = json.load(fi)
            fi.close()
        else:
            raise Exception('unsupported URL: %r' % url)

        if 'platform' in index and index['platform'] != self.plat:
            raise Exception('index file for platform %s, but running %s' %
                            (index['platform'], self.plat))

        if 'eggs' in index:
            self._add_egg_repos(url, index)

        self.index.append(index)

    def _add_egg_repos(self, url, index):
        if 'egg_repos' in index:
            repos = [url + path + '/' for path in index['egg_repos']]
        else:
            repos = [url]
        self.chain.repos.extend(repos)

        for cname, project in index['eggs'].iteritems():
            for distname, data in project['files'].iteritems():
                name, version, build = dist_naming.split_eggname(distname)
                spec = dict(metadata_version='1.1',
                            name=name, version=version, build=build,
                            python=data.get('python', '2.7'),
                            packages=data.get('depends', []))
                add_Reqs_to_spec(spec)
                assert spec['cname'] == cname, distname
                dist = repos[data.get('repo', 0)] + distname
                self.chain.index[dist] = spec
                self.chain.groups[cname].append(dist)

    def get_installed_cnames(self):
        if not self._installed_cnames:
            self._installed_cnames = egginst.get_installed_cnames(self.prefix)
        return self._installed_cnames

    def get_status(self):
        if not self._status:
            # the result is a dict mapping cname to ...
            res = {}
            for cname in self.get_installed_cnames():
                d = defaultdict(str)
                info = get_installed_info(self.prefix, cname)
                if info is None:
                    continue
                d.update(info)
                res[cname] = d

                for cname in self.chain.groups.iterkeys():
                    dist = self.chain.get_dist(Req(cname))
                    if dist is None:
                        continue
                    repo, fn = dist_naming.split_dist(dist)
                    n, v, b = dist_naming.split_eggname(fn)
                    if cname not in res:
                        d = defaultdict(str)
                        d['name'] = n
                        res[cname] = d
                    res[cname]['a-egg'] = fn
                    res[cname]['a-ver'] = '%s-%d' % (v, b)

            def vb_egg(fn):
                try:
                    n, v, b = dist_naming.split_eggname(fn)
                    return comparable_version(v), b
                except IrrationalVersionError:
                    return None

            for d in res.itervalues():
                if d['egg_name']:                    # installed
                    if d['a-egg']:
                        if vb_egg(d['egg_name']) >= vb_egg(d['a-egg']):
                            d['status'] = 'up-to-date'
                        else:
                            d['status'] = 'updateable'
                    else:
                        d['status'] = 'installed'
                else:                                # not installed
                    if d['a-egg']:
                        d['status'] = 'installable'
            self._status = res
        return self._status

    def get_installed(self):
        if not self._installed:
            self._installed = set([pkg['egg_name']
                                   for pkg in self.get_status().values()
                                   if pkg['status'] != 'installable'])
        return self._installed

    def install(self, req):
        # Convert cnames to Req instances
        if isinstance(req, str):
            req = Req(req)

        logger.debug('Installing %s' % req.name)

        # 1. get list of package and all its dependencies, as URLs to .eggs
        dists = [(dist, dist_naming.filename_dist(dist))
                 for dist in self.chain.install_sequence(req)]

        # 2. get list of currently installed packages
        installed = self.get_installed()

        # 3. download .eggs
        egg_storage = config.get('local')
        logger.debug('Storing dowloaded eggs at %s' % egg_storage)
        if not isdir(egg_storage):
            makedirs(egg_storage)
        for dist, eggname in dists:
            if eggname in installed:
                logger.debug('Skipping re-downloading %s' % eggname)
                continue
            logger.debug('Downloading %s' % eggname)
            self.chain.fetch_dist(dist, egg_storage)

        # 4. remove existing versions of packages to be installed
        for dist, eggname in reversed(dists):
            if eggname in installed:
                logger.debug('Skipping removing %s' % eggname)
                continue
            logger.debug('Removing old %s' % eggname)
            enstaller_main.prefix = self.prefix
            egginst_remove(cname_fn(eggname))

        # 5. install new versions of packages
        installed_count = 0
        for dist, eggname in dists:
            if eggname in installed:
                logger.debug('Skipping re-installing %s' % eggname)
                continue
            logger.debug('Installing %s' % eggname)
            installed_count += 1
            enstaller_main.prefix = self.prefix
            egginst_install(dist)

        # Clear the cache, since the status of several packages could now be
        # invalid
        self.clear_cache()

        return installed_count

    def uninstall(self, req):
        # Convert cnames to Req instances
        if isinstance(req, str):
            req = Req(req)

        enstaller_main.prefix = self.prefix
        egginst_remove(req.name)
        self.clear_cache()
        return 1


if __name__ == '__main__':
    #url = 'file://' + expanduser('~/buildware/scripts')
    url = 'https://EPDUser:Epd789@www.enthought.com/repo/epd/'
    r = Resources([url], verbose=1)

    req = Req('epd')
    print r.chain.get_dist(req)
    r.chain.print_repos()
    for v in r.get_status().itervalues():
        print '%(name)-20s %(version)16s %(a-ver)16s %(status)12s' % v
