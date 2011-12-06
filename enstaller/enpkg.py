import sys
from os.path import isdir, isfile, join

import egginst
from egginst.utils import pprint_fn_action, console_progress

from store.indexed import LocalIndexedStore, RemoteHTTPIndexedStore
from store.joined import JoinedStore

from plat import custom_plat
from resolve import Req, Resolve
from fetch import FetchAPI


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
            raise Exception("cannot create store from URL: %r" % url)
    return JoinedStore(stores)


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
        if hasattr(self, '_connected'):
            return
        self.remote.connect(self.userpass)
        self._connected = True

    def install_recur(self, egg, hook=False, force=False):
        self._connect()
        info = self.remote.get_metadata(egg)
        # todo: handle python version
        resolver = Resolve(self.remote, self.verbose)
        req = Req('%(name)s %(version)s-%(build)d' % info)
        for e in resolver.install_sequence(req):
            self.install(e, hook, force)

    def install(self, egg, hook=False, force=False):
        if not force and hook and isfile(self.registry_path_egg(egg)):
            if self.verbose:
                print "Already installed:", egg
            return
        egg_path = join(self.local_dir, egg)
        if force or not isfile(egg_path):
            self.fetch(egg, force)
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(egg_path, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install()

    def remove(self, egg, hook=False):
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
    x.install(fn, force=1)
