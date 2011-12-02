import sys
from os.path import isdir, isfile, join

import egginst
from egginst.utils import pprint_fn_action, console_progress

from store.local import LocalStore

from plat import custom_plat
import resolve
import fetch


class Resource(object):

    def __init__(self, remote, prefix=sys.prefix, plat=custom_plat,
                 verbose=False):
        self.remote = remote
        self.prefix = prefix
        self.plat = custom_plat
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.local = LocalStore(join(prefix, 'LOCAL-REPO'))
        self.pkgs_dir = join(prefix, 'pkgs')

    def get_installed_apps(self):
        return dict(self.local.query(app=True))

    def launch_app(self, egg):
        info = self.local.get_metadata(egg)
        print info

    def install_app(self, egg, force=False):
        self.install_recur(egg, True, force)

    def install_recur(self, egg, hook, force=False):
        info = self.remote.get_metadata(egg)
        # todo handle python version
        resolver = resolve.Resolve(self.remote, self.verbose)
        req = resolve.Req('%(name)s %(version)s-%(build)d' % info)
        for e in resolver.install_sequence(req):
            self.install(e, hook, force)

    def install(self, egg, hook, force=False):
        if not force and hook and isfile(self.registry_path_egg(egg)):
            if self.verbose:
                print "Already installed:", egg
            return
        egg_path = join(self.fetch_dir, egg)
        if force or not isfile(egg_path):
            self.fetch_egg(egg, force)
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(egg_path, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install()

    def remove(self, egg, hook):
        self.action_callback(egg, 'removing')
        ei = egginst.EggInst(egg, prefix=self.prefix, hook=hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.remove()

    def parse_registry_files(self, eggs):
        pth = []
        registry = {}
        for egg in eggs:
            for line in open(self.registry_path_egg(egg)):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                k, v = line.split(None, 1)
                if k == '-pth-':
                    if v not in pth:
                        pth.append(v)
                else:
                    registry[k] = v
        return pth, registry

    def registry_path_egg(self, egg):
        return join(self.versioned_dir_egg(egg), 'EGG-INFO', 'registry.txt')

    def versioned_dir_egg(self, egg):
        return join(self.pkgs_dir, egg[:-4])

    def fetch_egg(self, egg, force=False):
        f = fetch.FetchAPI(self.remote, self.local.root)
        f.action_callback = self.action_callback
        f.progress_callback = self.progress_callback
        f.verbose = self.verbose
        f.fetch_egg(egg, force)


if __name__ == '__main__':
    from store.indexed import LocalIndexedStore
    from store.joined import JoinedStore

    rem = JoinedStore([LocalIndexedStore('/Users/ischnell/repo'),
                       LocalIndexedStore('/Users/ischnell/repo2')])
    #rem = LocalIndexedStore('/home/ischnell/eggs/')
    rem.connect()
    prefix = '/Users/ischnell/jpm/Python-2.7.2-1'
    x = Resource(rem, prefix=prefix, verbose=1)
    #x.install('enstaller-4.5.0-1.egg')
    #x.remove('enstaller-4.5.0-1.egg')
    #x.install('nose-1.1.2-1.egg', 1, force=1)
    #for d in x.get_installed_apps():
    #    print d
    x.fetch_egg('nose-1.0.0-1.egg')
    x.fetch_egg('nose-1.1.2-1.egg')
    x.launch_app('nose-1.1.2-1.egg')

    y = Resource(LocalStore(prefix), prefix=prefix, verbose=1)
    y.launch_app('nose-1.1.2-1.egg')
