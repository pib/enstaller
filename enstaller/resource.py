import sys
import json
from collections import defaultdict
from httplib import HTTPConnection
import logging
from os import makedirs
from os.path import isdir, join, split, exists
import re
from urllib2 import HTTPError, urlopen, Request
from urlparse import urlsplit
from datetime import datetime

from traits.etsconfig.api import ETSConfig
import config
import egginst
from enstaller import Enstaller
from enstaller.history import History
from plat import custom_plat
from utils import open_with_auth, get_installed_info, comparable_version, \
    cname_fn
from verlib import IrrationalVersionError
from indexed_repo.chain import Chain, Req
from indexed_repo import dist_naming
from indexed_repo.requirement import add_Reqs_to_spec

logger = logging.getLogger(__name__)


class Resources(object):

    def __init__(self, index_root=None, urls=[], verbose=False, prefix=None,
                 platform=None):
        self.plat = platform or custom_plat
        self.prefix = prefix
        self.verbose = verbose
        self.index = []
        self.history = History(prefix)
        self.enst = Enstaller(Chain(verbose=verbose), [prefix or sys.prefix])
        self.product_index_path = 'products'
        self.authenticate = True

        # The prefix of the EPD installation to support multiple EPD installs.
        pref = '' if prefix is None else split(sys.prefix)[1]
        self._cache_dir = join(ETSConfig.application_data,'cache',pref)
        if not exists(self._cache_dir):
            makedirs(self._cache_dir)

        # The index cache file.
        self._cache_file = join(self._cache_dir, 'product_cache.json')
        try:
            with open(self._cache_file) as f:
                self._product_cache = json.load(f)
        except (IOError, ValueError):
            self._product_cache = {}

        for url in urls:
            self.add_product(url)

        if index_root:
            self.load_index(index_root)

        # Cache attributes
        self._installed_cnames = None
        self._status = None
        self._installed = None

    def clear_cache(self):
        self._installed_cnames = None
        self._status = None
        self._installed = None

    def _http_auth(self):
        username, password = config.get_auth()
        if username and password and self.authenticate:
            return (username + ':' + password).encode('base64')
        else:
            return None

    def _read_json_from_url(self, url):
        logger.debug('Reading JSON from URL: %s' % url)
        req = Request(url)
        auth = self._http_auth()
        if auth:
            req.add_header('Authorization', auth)
        return json.load(urlopen(req))

    def load_index(self, url):
        url = url.rstrip('/')
        index_url = '%s/%s' % (url, self.product_index_path)
        try:
            index = self._read_json_from_url(index_url)
        except HTTPError as e:
            logger.exception('Error getting products file %s' % index_url)
            return

        for product in index:
            product_name = product['product']
            product_url = '%s/products/%s' % (url, product_name)
            try:
                product['base_url'] = url
                product['url'] = product_url.rstrip('/')
                self.add_product(product)
                self._product_cache[product_name] = dict(
                    product=product_name,
                    last_update=product['last_update'],
                    url=product_url)
            except HTTPError:
                logger.exception('Error getting index file %s' % product_url)

        with open(self._cache_file, 'w') as f:
            json.dump(self._product_cache, f, indent=4)

    def _read_product_index_cached(self, index):
        """ Try to read product index from cache if it is updated. """
        use_cache = False
        cached_prod = self._product_cache.get(index['product'])
        cache_dir = join(self._cache_dir, index['product'])
        if cached_prod:
            fmt = '%Y-%m-%d %H:%M:%S'
            new_time = datetime.strptime(index['last_update'], fmt)
            old_time = datetime.strptime(cached_prod['last_update'], fmt)
            if new_time == old_time:
                # Try loading the product index from the cached files.
                for suffix in ('', '-' + self.plat):
                    cache_file = join(cache_dir, 'index%s.json' % suffix)
                    try:
                        return cache_file, json.load(open(cache_file))
                    except (ValueError, IOError) as e:
                        logger.error('Error loading product index cache - %s' %
                                     index['product'])
        else:
            # Ensure cache directory exists for writing new cache files.
            if not exists(cache_dir):
                makedirs(cache_dir)
        return None, None

    def _read_product_index(self, index):
        """ Get the product index.

        Try the platform-independent one first, then try the
        platform-specific one if that one doesn't exist. Does both
        HTTP requests simultaneously.

        """
        # Try to load index from cache.
        url, data = self._read_product_index_cached(index)
        if url is not None:
            return url, data

        product_url = index['url']
        independent = urlsplit('%s/index.json' % (product_url))
        specific = urlsplit('%s/index-%s.json' % (product_url, self.plat))
        logger.debug('Trying for JSON from URLs: %s, %s' %
                     (independent.geturl(), specific.geturl()))
        conn1 = HTTPConnection(independent.netloc)
        conn2 = HTTPConnection(specific.netloc)
        auth = self._http_auth()
        if auth:
            headers = {'Authorization': auth}
        else:
            headers = {}
        conn1.request('GET', independent.path, headers=headers)
        conn2.request('GET', specific.path, headers=headers)

        try:
            res = conn1.getresponse()
            if res.status == 200:
                data = res.read()
                cache_file = join(self._cache_dir, index['product'], 'index.json')
                with open(cache_file, 'wb') as f:
                    f.write(data)
                return independent, json.loads(data)
            res = conn2.getresponse()
            if res.status == 200:
                data = res.read()
                cache_file = join(self._cache_dir, index['product'],
                                  'index-%s.json' % self.plat)
                with open(cache_file, 'wb') as f:
                    f.write(data)
                return specific, json.loads(data)
            else:
                raise HTTPError(specific, res.status, res.reason, res.msg, None)

        except ValueError:
            logger.exception('Error parsing index for %s' % product_url)
            logger.error('Invalid index file: """%s"""' % data)
            return None, None
        except HTTPError:
            logger.exception('Error reading index for %s' % product_url)
            return None, None
        finally:
            conn1.close()
            conn2.close()

    def add_product(self, index):

        if self.verbose:
            print "Adding product:", index['url']

        index_url, product_index = self._read_product_index(index)
        if product_index is None:
            return

        index['index_url'] = index_url
        index.update(product_index)

        if 'platform' in index and index['platform'] != self.plat:
            raise Exception('index file for platform %s, but running %s' %
                            (index['platform'], self.plat))

        if 'eggs' in index:
            self._add_egg_repos(index['url'], index)

        self.index.append(index)
        return index

    def _add_egg_repos(self, url, index):
        if 'egg_repos' in index:
            repos = [url + '/' + path + '/' for path in index['egg_repos']]
        else:
            repos = [url]
        self.enst.chain.repos.extend(repos)

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
                self.enst.chain.index[dist] = spec
                self.enst.chain.groups[cname].append(dist)

    def get_installed_cnames(self):
        if not self._installed_cnames:
            self._installed_cnames = self.enst.get_installed_cnames()
        return self._installed_cnames

    def get_status(self):
        if not self._status:
            # the result is a dict mapping cname to ...
            res = {}
            for cname in self.get_installed_cnames():
                d = defaultdict(str)
                info = self.enst.get_installed_info(cname)[0][1]
                if info is None:
                    continue
                d.update(info)
                res[cname] = d

                for cname in self.enst.chain.groups.iterkeys():
                    dist = self.enst.chain.get_dist(Req(cname))
                    if dist is None:
                        continue
                    repo, fn = dist_naming.split_dist(dist)
                    n, v, b = dist_naming.split_eggname(fn)
                    if cname not in res:
                        d = defaultdict(str)
                        d['name'] = d.get('name', cname)
                        res[cname] = d
                    res[cname]['a-egg'] = fn
                    res[cname]['a-ver'] = '%s-%d' % (v, b)

            def vb_egg(fn):
                try:
                    n, v, b = dist_naming.split_eggname(fn)
                    return comparable_version(v), b
                except IrrationalVersionError:
                    return None
                except AssertionError:
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

    def search(self, text):
        """ Search for eggs with name or description containing the given text.

        Returns a list of canonical names for the matching eggs.
        """
        regex = re.compile(re.escape(text), re.IGNORECASE)
        results = []
        for product in self.index:
            for cname, metadata in product.get('eggs', {}).iteritems():
                name = metadata.get('name', '')
                description = metadata.get('description', '')
                if regex.search(name) or regex.search(description):
                    results.append(cname)
        return results

    def _req_list(self, reqs):
        """ Take a single req or a list of reqs and return a list of
        Req instances
        """
        if not isinstance(reqs, list):
            reqs = [reqs]

        # Convert cnames to Req instances
        for i, req in enumerate(reqs):
            if not isinstance(req, Req):
                reqs[i] = Req(req)
        return reqs

    def install(self, reqs):
        reqs = self._req_list(reqs)

        with self.history:
            installed_count = 0
            for req in reqs:
                installed_count += self.enst.install(req)

        # Clear the cache, since the status of several packages could now be
        # invalid
        self.clear_cache()

        return installed_count

    def uninstall(self, reqs):
        reqs = self._req_list(reqs)

        with self.history:
            for req in reqs:
                self.enst.remove(req)

        self.clear_cache()
        return 1


if __name__ == '__main__':
    #url = 'file://' + expanduser('~/buildware/scripts')
    url = 'https://EPDUser:Epd789@www.enthought.com/repo/epd/'
    r = Resources([url], verbose=1)

    req = Req('epd')
    print r.enst.chain.get_dist(req)
    r.enst.chain.print_repos()
    for v in r.get_status().itervalues():
        print '%(name)-20s %(version)16s %(a-ver)16s %(status)12s' % v
