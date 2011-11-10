import sys
import json
from collections import defaultdict
import logging
from os import makedirs, stat
from os.path import dirname, join, exists
import re
from urllib2 import urlopen, Request
from urlparse import urlsplit, urlunsplit
from datetime import datetime

import config
from enstaller import Enstaller
from enstaller.history import History
from enstaller.main import revert
from plat import custom_plat
from utils import comparable_version
from verlib import IrrationalVersionError
from indexed_repo.chain import Chain, Req
from indexed_repo import dist_naming
from indexed_repo.requirement import add_Reqs_to_spec

logger = logging.getLogger(__name__)


class EnstallerResourceIndexError(EnvironmentError):
    """ Raise when one or more Enstaller resource indices cannot be read.
    """
    def __init__(self, msg, exc):
        super(EnstallerResourceIndexError, self).__init__(msg)
        try:
            self.data = json.loads(exc.read())
        except:
            self.data = None

class ResourceCache(object):
    def __init__(self, cache_dir, root_url):
        self._cache_dir = cache_dir
        self._root_url = root_url
        self.authenticate = True

    def url_for(self, path):
        return '{}/{}'.format(self._root_url, path)

    def _http_auth(self):
        username, password = config.get_auth()
        if username and password and self.authenticate:
            return 'Basic ' + (username + ':' + password).encode('base64').strip()
        else:
            return None

    def _read_json_from_url(self, url):
        logger.debug('Reading JSON from URL: {}'.format(url))
        req = Request(url)
        auth = self._http_auth()
        if auth:
            req.add_unredirected_header('Authorization', auth)
        return json.load(urlopen(req))

    def get(self, path, last_update):
        """ Return the resource at the specified path, either from the
        cache file at cache_dir/path if it exists and is younger than
        last_update, or from download from root_url/path.

        If last_update is None, then always try to download and fall
        back to the file if it exists.

        Also, if the cache is recent enough, but the file can't be
        parsed (as JSON), then the URL is requested.

        - path (string) Path under the base url or cache directory to
                        attempt to download

        - last_update (datetime.datetime) Timestamp to check against
                                          cached file mtime
        """
        cache_file_path = join(self._cache_dir, path)
        if not cache_file_path.endswith('.json'):
            cache_file_path = cache_file_path.rstrip('/') + '.json'
        full_url = self.url_for(path)
        cached_data = None
        http_exc = None

        try:
            mtime = datetime.utcfromtimestamp(stat(cache_file_path).st_mtime)
            cache_file_valid = mtime > (last_update or 0)
        except:
            cache_file_valid = False

        # Read the file if it seems valid so far
        if cache_file_valid:
            try:
                logger.debug('Trying to load {}'.format(cache_file_path))
                cached_data = json.load(open(cache_file_path))
            except:
                logger.exception('Error reading cache file "{}"'
                                 .format(cache_file_path))
                cache_file_valid = False

        # If this is a timestamped cache request and the file was
        # valid, we're done.
        if last_update and cache_file_valid:
            return cached_data

        # Otherwise, try to read from URL
        try:
            logger.debug('Trying to load {}'.format(full_url))
            data = self._read_json_from_url(full_url)
        except Exception as e:
            if getattr(e, 'code', None) == 401:
                if last_update is None:
                    try:
                        data = json.loads(e.read())
                    except:
                        logger.exception('Dang')
                        data = None
                else:
                    http_exc = e
                    data = None
            else:
                logger.exception('Error reading from URL "{}"'.format(full_url))
                data = None

        # If we got valid data JSON data back, write the cache file and return
        if data:
            try:
                logger.debug('Trying to write out {}'.format(cache_file_path))
                cache_file_dir = dirname(cache_file_path)
                if not exists(cache_file_dir):
                    makedirs(cache_file_dir)
                json.dump(data, open(cache_file_path, 'w'))
            except:
                # Log the exception on error, but we already have the
                # data, so return that either way
                logger.exception('Error writing cache file "{}"'
                                 .format(cache_file_path))
            return data

        # As a last resort, return the contents of the cached file, if
        # it exists
        if cached_data:
            return cached_data
        try:
            logger.debug('Trying to load {}'.format(cache_file_path))
            return json.load(open(cache_file_path))
        except:
            logger.exception('Error reading cache file "{}"'
                             .format(cache_file_path))

        raise EnstallerResourceIndexError(
            "Couldn't load index file from '{}' or '{}'"
            .format(cache_file_path, full_url), http_exc)


class Resources(object):

    # FIXME: class and methods need docstrings.

    def __init__(self, index_root=None, urls=[], verbose=False, prefix=None,
                 platform=None):
        self.plat = platform or custom_plat
        self.prefix = prefix or sys.prefix
        self.verbose = verbose
        self.index = []   # list of dicts of product metadata
        self.history = History(self.prefix)
        self.enst = Enstaller(Chain(verbose=verbose), [self.prefix])
        self.product_list_path = 'products'

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

    def load_index(self, url_root):
        """ Append to self.index, the metadata for all products found
        at url_root
        """
        url_root = url_root.rstrip('/')
        self._product_cache = ResourceCache(join(self.prefix, 'cache'),
                                            url_root)

        try:
            product_list = self._product_cache.get(self.product_list_path + '/',
                                                   None)
        except EnstallerResourceIndexError as e:
            if e.data:
                product_list = e.data
            else:
                raise

        filtered_product_list = {}
        for product in product_list:
            slug = product['repo_slug']
            if slug not in filtered_product_list or (
                    (not filtered_product_list[slug]['subscribed'])
                    and product['subscribed']):
                filtered_product_list[slug] = product

        for product_metadata in [pm for pm in product_list if
                                 filtered_product_list[pm['repo_slug']] == pm]:
            self._add_product(product_metadata)

    def _add_product(self, product_metadata):
        """ Append a dict of product metadata to self.index after
        filling in the full product metadata
        """
        if self.verbose:
            print "Adding product:", product_metadata['product']

        self._read_full_product_metadata(product_metadata)

        if ('platform' in product_metadata and
            product_metadata['platform'] != self.plat):
            raise Exception('Product metadata file for {}, but running {}'
                            .format(product_metadata['platform'], self.plat))

        if 'eggs' in product_metadata:
            self._add_egg_repos(product_metadata['url'], product_metadata)
        else:
            product_metadata['eggs'] = {}

        self.index.append(product_metadata)

    def _read_full_product_metadata(self, product_metadata):
        """ Given partial product metadata, fill in full product metatadata
        which includes a list of the resources (e.g. eggs) which it includes.

        Fills in the product_metadata dict in place.
        """
        product_path = '{}/{}'.format(self.product_list_path,
                                      product_metadata['product'])
        product_metadata['url'] = self._product_cache.url_for(product_path)
        parts = urlsplit(product_metadata['url'])
        if product_metadata['product'] == 'EPDFree':
            path = 'account/register/'
        else:
            path = 'products/{0}/'.format(product_metadata['product'])
        product_metadata['buy_url'] = urlunsplit((parts.scheme, parts.netloc,
                                                  path, '', ''))

        if product_metadata.get('platform_independent', False):
            index_filename = 'index.json'
        else:
            index_filename = 'index-{}.json'.format(self.plat)
        product_index_path = '{}/{}'.format(product_path, index_filename)
        last_update = datetime.strptime(product_metadata['last_update'],
                                        '%Y-%m-%d %H:%M:%S')

        product_info = self._product_cache.get(product_index_path, last_update)
        product_metadata.update(product_info)

    def _add_egg_repos(self, url, product_metadata):
        if 'egg_repos' in product_metadata:
            repos = ['{}/{}/'.format(url, path)
                     for path in product_metadata['egg_repos']]
        else:
            repos = [url]
        self.enst.chain.repos.extend(repos)

        if not product_metadata['subscribed']:
            for repo in repos:
                self.enst.chain.unsubscribed_repos[repo] = product_metadata

        for cname, project in product_metadata['eggs'].iteritems():
            for distname, data in project['files'].iteritems():
                name, version, build = dist_naming.split_eggname(distname)
                spec = dict(metadata_version='1.1',
                            name=name, version=version, build=build,
                            python=data.get('python', '2.7'),
                            packages=data.get('depends', []),
                            size=data.get('size'))
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
                dist = self.enst.chain.get_dist(Req(cname),
                                                allow_unsubscribed=True)
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
        for product_metadata in self.index:
            for cname, metadata in product_metadata.get('eggs', {}).iteritems():
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

    def install(self, reqs, overall_progress_cb=None):
        reqs = self._req_list(reqs)

        full_reqs = self.enst.full_install_sequence(reqs)
        total_count = len(full_reqs)
        with self.history:
            installed_count = 0
            for req in full_reqs:
                installed_count += self.enst.install(req)
                if overall_progress_cb:
                    overall_progress_cb(installed_count, total_count)

        # Clear the cache, since the status of several packages could now be
        # invalid
        self.clear_cache()

        return installed_count

    def uninstall(self, reqs, overall_progress_cb=None):
        reqs = self._req_list(reqs)

        total_count = len(reqs)
        with self.history:
            removed_count = 0
            for req in reqs:
                self.enst.remove(req)
                removed_count += 1
                if overall_progress_cb:
                    overall_progress_cb(removed_count, total_count)

        self.clear_cache()
        return 1

    def revert(self, revert_to):
        revert(self.enst, str(revert_to), quiet=True)
        self.clear_cache()

if __name__ == '__main__':
    # FIXME: this section no longer matches the Resources class. Remove or revise.
    #url = 'file://' + expanduser('~/buildware/scripts')
    url = 'https://EPDUser:Epd789@www.enthought.com/repo/epd/'
    r = Resources([url], verbose=1)

    req = Req('epd')
    print r.enst.chain.get_dist(req)
    r.enst.chain.print_repos()
    for v in r.get_status().itervalues():
        print '%(name)-20s %(version)16s %(a-ver)16s %(status)12s' % v
