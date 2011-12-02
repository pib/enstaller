import os
from os.path import isdir, isfile, join

from egginst.utils import pprint_fn_action, console_progress

from store.local import LocalStore
from store.cache import CacheStore

from utils import stream_to_file, md5_file


class FetchAPI(object):

    def __init__(self, remote, local_dir):
        self.remote = remote
        self.local_dir = local_dir

        self.action_callback = pprint_fn_action
        self.progress_callback = console_progress
        self.verbose = False
        self.force = False

        self.local = LocalStore(self.local_dir)
        self.repo = CacheStore(remote, self.local)

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
            assert info['dst'] == egg
            src_path = join(self.local_dir, info['src'])
            #print '%8d %s %s' % (info['size'], patch_fn, isfile(src_path))
            if isfile(src_path):
                possible.append((info['size'], patch_fn, info))

        if not possible:
            return False
        size, patch_fn, info = min(possible)

        patch_path = join(self.local_dir, patch_fn)
        self.action_callback(patch_fn, 'fetching')
        #self.local.set(patch_fn, self.remote.get(patch_fn))
        stream_to_file(self.repo.get_data(patch_fn), patch_path,
                       info, self.progress_callback)

        self.action_callback(info['src'], 'patching')
        zdiff.patch(join(self.local_dir, info['src']),
                    join(self.local_dir, egg), patch_path,
                    self.progress_callback)
        self.local.set_metadata(egg, self.remote.get_metadata(egg))
        return True

    def fetch_egg(self, egg):
        """
        fetch an egg, i.e. copy or download the distribution into
        self.local_dir.
        force: force download or copy if MD5 mismatches
        """
        if not isdir(self.local_dir):
            os.makedirs(self.local_dir)
        info = self.repo.get_metadata(egg)
        path = join(self.local_dir, egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if self.force:
                if md5_file(path) == info.get('md5'):
                    if self.verbose:
                        print "Not refetching, %r MD5 match" % path
                    return
            else:
                if self.verbose:
                    print "Not forcing refetch, %r exists" % path
                return

        if not self.force and self.patch_egg(egg):
            return

        self.action_callback(egg, 'fetching')
        #self.local.set(egg, self.remote.get(egg))
        stream_to_file(self.repo.get_data(egg), path, info,
                       self.progress_callback)


if __name__ == '__main__':
    from store.indexed import LocalIndexedStore
    from store.joined import JoinedStore

    rem = JoinedStore([LocalIndexedStore('/Users/ischnell/repo'),
                       LocalIndexedStore('/Users/ischnell/repo2')])
    rem.connect()
    x = FetchAPI(rem, '/Users/ischnell/jpm/repo')
    x.verbose = True
    x.fetch_egg('nose-1.0.0-1.egg')
    x.fetch_egg('nose-1.1.2-1.egg')
