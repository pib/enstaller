import sys
import json
from os.path import isdir, isfile, join

import egginst
from egginst.utils import pprint_fn_action, console_progress

from store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from store.joined import JoinedStore

from utils import comparable_version
from plat import custom_plat
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


def name_egg(egg):
    n, v, b = split_eggname(egg)
    return n.lower()


class Enpkg(object):

    def __init__(self, urls, userpass=None,
                 prefix=sys.prefix, plat=custom_plat,
                 verbose=False):
        self.remote = create_joined_store(urls)
        self.userpass = userpass
        self.prefix = prefix
        self.plat = custom_plat
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.local_dir = join(prefix, 'LOCAL-REPO')
        self.pkgs_dir = join(prefix, 'pkgs')

    def _connect(self):
        if getattr(self, '_connected', None):
            return
        self.remote.connect(self.userpass)
        self._connected = True

    def query(self, **kwargs):
        self._connect()
        kwargs['type'] = 'egg'
        for egg, info in self.remote.query(**kwargs):
            yield egg, info

    def list_versions(self, name):
        req = Req(name)
        info_repo_list = []
        for key, info in self.query(name=name):
            if req.matches(info):
                repo = self.remote.from_which_repo(key)
                info_repo_list.append((info, repo.info()['dispname']))
        sortfunc = lambda ir: comparable_version(ir[0]['version'])
        try:
            return sorted(info_repo_list, key=sortfunc)
        except TypeError:
            return list(info_repo_list)

    def filter_installed(self, eggs, hook=False):
        res = []
        for egg in eggs:
            if hook:
                if self.info_installed_egg(egg):
                    continue
            else: # no hook
                info = self.info_installed_name(name_egg(egg))
                if info['key'] == egg:
                    continue
            res.append(egg)
        return res

    def install(self, arg, mode='recur', hook=False,
                force=False, forceall=False):
        if isinstance(arg, Req):
            req = arg
        elif is_valid_eggname(arg):
            req = Req('%(name)s %(version)s-%(build)d' % split_eggname(arg))
        else:
            req = Req(arg)
        # resolve the list of eggs that need to be installed
        self._connect()
        resolver = Resolve(self.remote, self.verbose)
        eggs = resolver.install_sequence(req, mode)

        if not forceall:
            # filter installed eggs
            if force:
                first_eggs, last_egg = eggs[:-1], eggs[-1]
                eggs = self.filter_installed(first_eggs, hook) + [last_egg]
            else:
                eggs = self.filter_installed(eggs, hook)

        # fetch eggs
        for egg in eggs:
            self.fetch(egg, force or forceall)

        if not hook:
            # remove packages (in reverse install order)
            for egg in reversed(eggs):
                info = self.info_installed_name(name_egg(egg))
                if info:
                    self.remove_egg(info['key'])
        # install eggs
        for egg in eggs:
            self.install_egg(egg, hook)
        return len(eggs)

    def info_installed_name(self, name): # no hook
        assert name == name.lower()
        return self._installed_info_from_path(join(
                self.prefix, 'EGG-INFO', name, 'info.json'))

    def info_installed_egg(self, egg): # hook
        n, v, b = split_eggname(egg)
        return self._installed_info_from_path(join(
                self.pkgs_dir, '%s-%s-%d' % (n.lower(), v, b),
                'EGG-INFO', 'info.json'))

    def _installed_info_from_path(self, path):
        if isfile(path):
            info = json.load(open(path))
            info['installed'] = True
            return info
        return None

    def install_egg(self, egg, hook=False):
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(join(self.local_dir, egg),
                             prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install()

    def remove_egg(self, egg, hook=False):
        self.action_callback(egg, 'removing')
        ei = egginst.EggInst(egg, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.remove()

    def fetch(self, egg, force=False):
        self._connect()
        f = FetchAPI(self.remote, self.local_dir)
        f.action_callback = self.action_callback
        f.progress_callback = self.progress_callback
        f.verbose = self.verbose
        f.fetch_egg(egg, force)


if __name__ == '__main__':
    x = Enpkg(['/home/ischnell/eggs/'], verbose=1)
    fn = 'SimPy-2.2-2.egg'
    x.install_egg(fn, force=1)
