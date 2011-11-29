# Author: Ilan Schnell <ischnell@enthought.com>
import os
from os.path import isfile, join

from egginst.utils import pprint_fn_action, console_progress
from utils import stream_to_file, md5_file


class Fetch(object):
    """
    egg fetch API
    """
    def __init__(self, egg_repo, patch_repo=None, fetch_dir=os.getcwd(),
                 verbose=False):
        self.egg_repo = egg_repo
        self.patch_repo = patch_repo
        self.fetch_dir = fetch_dir
        self.verbose = verbose

        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

    def patch_egg(self, egg):
        """
        Try to create 'egg' by patching an already existing egg, returns
        True on success and False on failure, i.e. when either:
            - bsdiff4 is not installed
            - no patches can be applied (because the source is missing)
        """
        try:
            import enstaller.zdiff as zdiff
        except ImportError:
            if self.verbose:
                print "Warning: could not import bsdiff4, cannot patch"
            return False

        possible = []
        for patch_fn, info in self.patch_repo.query(name=egg.split('-')[0],
                                                    dst=egg):
            assert info['dst'] == egg
            src_path = join(self.fetch_dir, info['src'])
            #print '%8d %s %s' % (info['size'], patch_fn, isfile(src_path))
            if isfile(src_path):
                possible.append((info['size'], patch_fn, info))

        if not possible:
            return False
        size, patch_fn, info = min(possible)

        self.action_callback(patch_fn, 'fetching')
        patch_path = join(self.fetch_dir, patch_fn)
        stream_to_file(self.patch_repo.get(patch_fn), patch_path,
                       info, self.progress_callback)

        self.action_callback(info['src'], 'patching')
        zdiff.patch(join(self.fetch_dir, info['src']),
                    join(self.fetch_dir, egg), patch_path,
                    self.progress_callback)
        return True


    def fetch_egg(self, egg, force=False):
        """
        Get a distribution, i.e. copy or download the distribution into
        fetch_dir.

        force:
            force download or copy if MD5 mismatches
        """
        info = self.egg_repo.get_metadata(egg)
        path = join(self.fetch_dir, egg)

        # if force is used, make sure the md5 is the expected, otherwise
        # merely see if the file exists
        if isfile(path):
            if force:
                if md5_file(path) == info.get('md5'):
                    if self.verbose:
                        print "Not forcing refetch, %r MD5 match" % path
                    return
            else:
                if self.verbose:
                    print "Not forcing refetch, %r exists" % path
                return

        if (not force and self.patch_repo and self.patch_egg(egg)):
            return

        self.action_callback(egg, 'fetching')
        stream_to_file(self.egg_repo.get(egg), path, info,
                       self.progress_callback)


if __name__ == '__main__':
    from repo.indexed import LocalIndexedRepo
    from repo.chained import ChainedRepo

    r1 = ChainedRepo([LocalIndexedRepo('/Users/ischnell/repo'),
                     LocalIndexedRepo('/Users/ischnell/repo2')])
#    r1 = LocalIndexedRepo('/Users/ischnell/repo/')
    r1.connect()

    r2 = LocalIndexedRepo('/Users/ischnell/repo/patches/')
    r2.connect()

    f = Fetch(r1, r2, '/Users/ischnell/foo/z', verbose=1)
    f.fetch_egg('nose-1.0.0-1.egg', 0)
    f.fetch_egg('nose-1.1.2-1.egg', 1)
    f.fetch_egg('Qt-4.7.2-2.egg', 1)
    f.fetch_egg('Qt-4.7.3-1.egg', 0)
