import sys
from os.path import isdir, join

from store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from store.joined import JoinedStore

from eggcollect import EggCollection, JoinedEggCollection

from utils import comparable_version
from resolve import Req, Resolve
from fetch import FetchAPI
from egg_meta import is_valid_eggname, split_eggname


def create_joined_store(urls):
    stores = []
    for url in urls:
        if url.startswith('file://'):
            stores.append(LocalIndexedStore(url[7:]))
        elif url.startswith(('http://', 'https://')):
            stores.append(RemoteHTTPIndexedStore(url))
        elif isdir(url):
            stores.append(LocalIndexedStore(url))
        else:
            raise Exception("cannot create store: %r" % url)
    return JoinedStore(stores)

def req_from_anything(arg):
    if isinstance(arg, Req):
        return arg
    if is_valid_eggname(arg):
        return Req('%s %s-%d' % split_eggname(arg))
    return Req(arg)

def name_egg(egg):
    n, v, b = split_eggname(egg)
    return n.lower()

class EnpkgError(Exception):
    pass


class Enpkg(object):

    def __init__(self, remote, userpass=None,
                 prefixes=[sys.prefix], hook=False, verbose=False):
        self.remote = remote
        self.userpass = userpass
        self.prefixes = prefixes
        self.hook = hook
        self.verbose = verbose

        self.ec = JoinedEggCollection([EggCollection(prefix, self.hook)
                                       for prefix in self.prefixes])
        self.local_dir = join(self.prefixes[0], 'LOCAL-REPO')

    # ============= methods which relate to remove store =================

    def _connect(self):
        if getattr(self, '_connected', None):
            return
        self.remote.connect(self.userpass)
        self._connected = True

    def query_remote(self, **kwargs):
        self._connect()
        kwargs['type'] = 'egg'
        return self.remote.query(**kwargs)

    def info_list_name(self, name):
        req = Req(name)
        info_list = []
        for key, info in self.query_remote(name=name):
            if req.matches(info):
                repo = self.remote.where_from(key)
                info['repo_dispname'] = repo.info()['dispname']
                info_list.append(dict(info))
        try:
            return sorted(info_list,
                      key=lambda info: comparable_version(info['version']))
        except TypeError:
            return info_list

    # ============= methods which relate to local installation ===========

    def query_installed(self, **kwargs):
        return self.ec.query(**kwargs)

    def find(self, egg):
        return self.ec.find(egg)

    def install(self, arg, mode='recur', force=False, forceall=False):
        req = req_from_anything(arg)
        # resolve the list of eggs that need to be installed
        self._connect()
        resolver = Resolve(self.remote, self.verbose)
        eggs = resolver.install_sequence(req, mode)
        if eggs is None:
             raise EnpkgError("No egg found for requirement '%s'." % req)

        if not forceall:
            # remove already installed eggs from egg list
            rm = lambda eggs: [e for e in eggs if self.find(e) is None]
            if force:
                eggs = rm(eggs[:-1]) + [eggs[-1]]
            else:
                eggs = rm(eggs)

        # fetch eggs
        for egg in eggs:
            self.fetch(egg, force or forceall)

        if not self.hook:
            # remove packages with the same name (from first egg collection
            # only, in reverse install order)
            for egg in reversed(eggs):
                try:
                    self.remove(Req(name_egg(egg)))
                except EnpkgError:
                    pass

        # install eggs
        for egg in eggs:
            extra_info = {}
            repo = self.remote.where_from(egg)
            if repo:
                extra_info['repo_dispname'] = repo.info()['dispname']
            self.ec.install(egg, self.local_dir, extra_info)
        return len(eggs)

    def remove(self, req):
        assert req.name
        index = dict(self.ec.collections[0].query(**req.as_dict()))
        if len(index) == 0:
            raise EnpkgError("Package %s not installed in: %r" %
                              (req, self.prefixes[0]))
        if len(index) > 1:
            assert self.hook
            versions = ['%(version)s-%(build)d' % d
                        for d in index.itervalues()]
            raise EnpkgError("Package %s installed more than once: %s" %
                              (req.name, ', '.join(versions)))
        egg = index.keys()[0]
        self.ec.remove(egg)

    # == methods which relate to both (remote store / local installation ==

    def query(self, **kwargs):
        index = dict(self.query_remote(**kwargs))
        index.update(self.query_installed(**kwargs))
        return index.iteritems()

    def fetch(self, egg, force=False):
        self._connect()
        f = FetchAPI(self.remote, self.local_dir)
        f.verbose = self.verbose
        f.fetch_egg(egg, force)
