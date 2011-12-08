import sys
from os.path import isdir, join

from egginst.utils import pprint_fn_action, console_progress

from store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from store.joined import JoinedStore

from eggcollect import EggCollection, JoinedEggCollection

from utils import comparable_version
from resolve import Req, Resolve
from fetch import FetchAPI
from egg_meta import split_eggname


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

def name_egg(egg):
    n, v, b = split_eggname(egg)
    return n.lower()

class EggNotFound(Exception):
    pass


class Enpkg(object):

    def __init__(self, urls, userpass=None,
                 prefixes=[sys.prefix], hook=False, verbose=False):
        self.remote = create_joined_store(urls)
        self.userpass = userpass
        self.prefixes = prefixes
        self.hook = hook
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.ec = JoinedEggCollection([EggCollection(prefix, self.hook)
                                        for prefix in self.prefixes])
        self.local_dir = join(self.prefixes[0], 'LOCAL-REPO')

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
                repo = self.remote.from_which_repo(key)
                info['repo_dispname'] = repo.info()['dispname']
                info_list.append(dict(info))
        try:
            return sorted(info_list,
                      key=lambda info: comparable_version(info['version']))
        except TypeError:
            return info_list

    def query_installed(self, **kwargs):
        return self.ec.query(**kwargs)

    def filter_installed(self, eggs):
        return [egg for egg in eggs if self.ec.get_meta(egg) is None]

    def install(self, req, mode='recur', force=False, forceall=False):
        # resolve the list of eggs that need to be installed
        self._connect()
        resolver = Resolve(self.remote, self.verbose)
        eggs = resolver.install_sequence(req, mode)
        if eggs is None:
             raise EggNotFound("No egg found for requirement '%s'." % req)

        if not forceall:
            # filter installed eggs
            if force:
                eggs = self.filter_installed(eggs[:-1]) + [eggs[-1]]
            else:
                eggs = self.filter_installed(eggs)

        # fetch eggs
        for egg in eggs:
            self.fetch(egg, force or forceall)

        if not self.hook:
            # remove packages (in reverse install order)
            for egg in reversed(eggs):
                info = self.ec.get_meta_name(name_egg(egg))
                if info:
                    self.ec.remove(info['key'])

        # install eggs
        for egg in eggs:
            extra_info = {}
            repo = self.remote.from_which_repo(egg)
            if repo:
                extra_info['repo_dispname'] = repo.info()['dispname']
            self.ec.install(egg, self.local_dir, extra_info)
        return len(eggs)

    def remove(self, req):
        if self.hook:
            # XXX
            return

        info  = self.ec.get_meta_name(req.name)
        if info is None:
            raise EggNotFound("Package %r does not seem to be installed." %
                              req.name)
        self.ec.remove(info['key'])

    def fetch(self, egg, force=False):
        self._connect()
        f = FetchAPI(self.remote, self.local_dir)
        f.action_callback = self.action_callback
        f.progress_callback = self.progress_callback
        f.verbose = self.verbose
        f.fetch_egg(egg, force)
