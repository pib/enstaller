import math
import os
import sys
import hashlib
from uuid import uuid4
from os.path import basename, isdir, isfile, join

from egginst.utils import human_bytes, rm_rf
from utils import md5_file


class FetchAPI(object):

    def __init__(self, remote, local_dir, evt_mgr=None):
        self.remote = remote
        self.local_dir = local_dir
        self.evt_mgr = evt_mgr
        self.verbose = False

    def path(self, fn):
        return join(self.local_dir, fn)

    def fetch(self, key):
        path = self.path(key)
        fi, info = self.remote.get(key)

        size = info['size']
        md5 = info.get('md5')

        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from egginst.console import ProgressManager

        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="fetching",
                steps=size,
                # ---
                progress_type="fetching", filename=basename(path),
                disp_amount=human_bytes(size),
                super_id=getattr(self, 'super_id', None))

        n = 0
        h = hashlib.new('md5')
        if size < 256:
            buffsize = 1
        else:
            buffsize = 2 ** int(math.log(size / 256.0) / math.log(2.0) + 1)

        pp = path + '.part'
        if sys.platform == 'win32':
            rm_rf(pp)
        with progress:
            with open(pp, 'wb') as fo:
                while True:
                    chunk = fi.read(buffsize)
                    if not chunk:
                        break
                    fo.write(chunk)
                    if md5:
                        h.update(chunk)
                    n += len(chunk)
                    progress(step=n)
        fi.close()

        if md5 and h.hexdigest() != md5:
            raise ValueError("received data MD5 sums mismatch")

        if sys.platform == 'win32':
            rm_rf(path)
        os.rename(pp, path)

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
        for patch_fn, info in self.remote.query(
                          type='patch',
                          name=egg.split('-')[0].lower(),
                          dst=egg):
            assert info['dst'] == egg
            src_path = self.path(info['src'])
            #print '%8d %s %s' % (info['size'], patch_fn, isfile(src_path))
            if isfile(src_path):
                possible.append((info['size'], patch_fn, info))

        if not possible:
            return False
        size, patch_fn, info = min(possible)

        self.fetch(patch_fn)
        zdiff.patch(self.path(info['src']), self.path(egg),
                    self.path(patch_fn), self.evt_mgr,
                    super_id=getattr(self, 'super_id', None))
        return True

    def fetch_egg(self, egg, force=False):
        """
        fetch an egg, i.e. copy or download the distribution into local dir
        force: force download or copy if MD5 mismatches
        """
        if not isdir(self.local_dir):
            os.makedirs(self.local_dir)
        info = self.remote.get_metadata(egg)
        path = self.path(egg)

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

        self.fetch(egg)


def main():
    from optparse import OptionParser
    import store.indexed as indexed
    from egg_meta import is_valid_eggname

    p = OptionParser(usage="usage: %prog [options] ROOT_URL [EGG ...]",
                     description="simple interface to fetch eggs")
    p.add_option("--auth",
                 action="store",
                 help="username:password")
    p.add_option("--dst",
                 action="store",
                 help="destination directory",
                 default=os.getcwd(),
                 metavar='PATH')
    p.add_option("--force",
                 action="store_true")
    p.add_option('-v', "--verbose", action="store_true")

    opts, args = p.parse_args()

    if len(args) < 1:
        p.error('at least one argument (the repo root URL) expected, try -h')

    repo_url = args[0]
    if repo_url.startswith(('http://', 'https://')):
        store = indexed.RemoteHTTPIndexedStore(repo_url)
    else:
        store = indexed.LocalIndexedStore(repo_url)

    store.connect(tuple(opts.auth.split(':', 1)) if opts.auth else None)

    f = FetchAPI(store, opts.dst)
    f.verbose = opts.verbose
    for fn in args[1:]:
        if not is_valid_eggname(fn):
            raise Exception('Error: invalid egg name: %r' % fn)
        f.fetch_egg(fn, opts.force)


if __name__ == '__main__':
    main()
