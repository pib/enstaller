import os
import sys
import json
from glob import glob
from os.path import basename, dirname, isdir, isfile, join

import egginst
from egginst.utils import pprint_fn_action, console_progress

from store.local import LocalStore
from store.cache import CacheStore

from plat import custom_plat
from utils import stream_to_file, md5_file
from egg_meta import parse_rawspec
import resolve


def info_from_install(meta_dir):
    res = dict(type='egg')
    path = join(meta_dir, 'spec', 'depend')
    res.update(parse_rawspec(open(path).read()))

    path = join(meta_dir, 'app.json')
    if isfile(path):
        res['app'] = True
        res.update(json.load(open(path)).iteritems())

    path = join(meta_dir, '__egginst__.json')
    return json.load(open(path))['egg_name'], res


class Resource(object):

    def __init__(self, remote, prefix=sys.prefix, plat=custom_plat,
                 verbose=False):
        self.prefix = prefix
        self.plat = custom_plat
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.fetch_dir = join(prefix, 'LOCAL-REPO')
        self.pkgs_dir = join(prefix, 'pkgs')

        self.remote = remote
        self.local = LocalStore(self.fetch_dir)
        self.repo = CacheStore(remote, self.local)

    def get_installed_apps(self):
        for p in glob(join(self.pkgs_dir, '*', 'EGG-INFO', 'app.json')):
            yield info_from_install(dirname(p))

    def launch_app(self, egg):
        info = info_from_install(join(self.pkgs_dir, egg[:-4], 'EGG-INFO'))
        print info

    def install_app(self, egg, force=False):
        self.install_recur(egg, True, force)

    def install_recur(self, egg, hook, force=False):
        info = self.repo.get_metadata(egg)
        # todo handle python version
        resolver = resolve.Resolve(self.repo, self.verbose)
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

    def patch_egg(self, egg):
        """
        Try to create 'egg' by patching an already existing egg, returns
        True on success and False on failure, i.e. when either:
            - bsdiff4 is not installed
            - no patches can be applied because: (i) there are no relevant
              patches in the repo (ii) a source egg is missing
        """
        try:
            import enstaller.zdiff as zdiff
        except ImportError:
            if self.verbose:
                print "Warning: could not import bsdiff4, cannot patch"
            return False

        possible = []
        for patch_fn, info in self.repo.query(type='patch',
                                              name=egg.split('-')[0].lower(),
                                              dst=egg):
            print patch_fn
            assert info['dst'] == egg
            src_path = join(self.fetch_dir, info['src'])
            #print '%8d %s %s' % (info['size'], patch_fn, isfile(src_path))
            if isfile(src_path):
                possible.append((info['size'], patch_fn, info))

        if not possible:
            return False
        size, patch_fn, info = min(possible)

        patch_path = join(self.fetch_dir, patch_fn)
        self.action_callback(patch_fn, 'fetching')
        self.local.set(patch_fn, self.remote.get(patch_fn))
        #stream_to_file(self.repo.get_data(patch_fn), patch_path,
        #               info, self.progress_callback)

        self.action_callback(info['src'], 'patching')
        zdiff.patch(join(self.fetch_dir, info['src']),
                    join(self.fetch_dir, egg), patch_path,
                    self.progress_callback)
        self.local.set_metadata(egg, self.remote.get_metadata(egg))
        return True

    def fetch_egg(self, egg, force=False):
        """
        fetch an egg, i.e. copy or download the distribution into
        self.fetch_dir.
        force: force download or copy if MD5 mismatches
        """
        if not isdir(self.fetch_dir):
            os.makedirs(self.fetch_dir)
        info = self.repo.get_metadata(egg)
        path = join(self.fetch_dir, egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if force:
                if md5_file(path) == info.get('md5'):
                    if self.verbose:
                        print "Not refetching, %r MD5 match" % path
                    return
            else:
                if self.verbose:
                    print "Not forcing refetch, %r exists" % path
                return

        if not force and self.patch_egg(egg):
            return

        self.action_callback(egg, 'fetching')
        self.local.set(egg, self.remote.get(egg))
        #stream_to_file(self.repo.get_data(egg), path, info,
        #               self.progress_callback)


if __name__ == '__main__':
    from store.indexed import LocalIndexedStore
    from store.joined import JoinedStore

    #r = ChainedRepo([LocalIndexedStore('/Users/ischnell/repo'),
    #                 LocalIndexedStore('/Users/ischnell/repo2')])
    r = LocalIndexedStore('/home/ischnell/eggs/')
    r.connect()
    #x = Resource(r, prefix='/Users/ischnell/jpm/Python-2.7.2-1', verbose=1)
    x = Resource(r, prefix='/home/ischnell/jpm/Python-2.7', verbose=1)
    #x.install('enstaller-4.5.0-1.egg')
    #x.remove('enstaller-4.5.0-1.egg')
    #x.install('nose-1.1.2-1.egg', 1, force=1)
    #for d in x.get_installed_apps():
    #    print d
    #x.launch_app('nose-1.1.2-1.egg')
    x.fetch_egg('nose-1.0.0-2.egg')
    x.fetch_egg('nose-1.1.2-1.egg', 1)
