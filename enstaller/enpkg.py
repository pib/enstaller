import sys
from os.path import isdir, join

from egginst.utils import pprint_fn_action, console_progress

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

    def find_name(self, egg):
        return self.ec.find_name(egg)

    def install(self, arg, mode='recur', force=False, forceall=False):
        req = req_from_anything(arg)
        # resolve the list of eggs that need to be installed
        self._connect()
        resolver = Resolve(self.remote, self.verbose)
        eggs = resolver.install_sequence(req, mode)
        if eggs is None:
             raise EggNotFound("No egg found for requirement '%s'." % req)

        if not forceall:
            # remove installed eggs from egg list
            rm = lambda eggs: [e for e in eggs if self.find(e) is None]
            if force:
                eggs = rm(eggs[:-1]) + [eggs[-1]]
            else:
                eggs = rm(eggs)

        # fetch eggs
        for egg in eggs:
            self.fetch(egg, force or forceall)

        if not self.hook:
            # remove packages (in reverse install order)
            for egg in reversed(eggs):
                info = self.find_name(name_egg(egg))
                if info:
                    self.ec.remove(info['key'])

        # install eggs
        for egg in eggs:
            extra_info = {}
            repo = self.remote.where_from(egg)
            if repo:
                extra_info['repo_dispname'] = repo.info()['dispname']
            self.ec.install(egg, self.local_dir, extra_info)
        return len(eggs)

    def remove(self, req):
        if self.hook:
            # XXX
            return

        info  = self.find_name(req.name)
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
