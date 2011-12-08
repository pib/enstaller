import os
import hashlib
from os.path import isdir, isfile, join

from egginst.utils import pprint_fn_action, console_progress

from utils import md5_file


class MD5Mismatch(Exception):
    pass


def stream_to_file(fi, path, info={}, progress_callback=None):
    """
    Read data from the filehandle and write a the file.
    Optionally check the MD5.  When the size in bytes and
    progress_callback are provided, the callback is called
    with progress updates as the download/copy occurs. If no size is
    provided, the callback will be called with None for the total
    size.

    The callback will be called with 0% progress at the beginning and
    100% progress at the end, so these two states can be used for any
    initial and final display.

    progress_callback signature: callback(so_far, total, state)
      so_far -- bytes so far
      total -- bytes total, if known, otherwise None
    """
    size = info.get('size')
    md5 = info.get('md5')

    if progress_callback is not None and size:
        n = 0
        progress_callback(0, size)

    h = hashlib.new('md5')
    if size and size < 16384:
        buffsize = 1
    else:
        buffsize = 256

    with open(path + '.part', 'wb') as fo:
        while True:
            chunk = fi.read(buffsize)
            if not chunk:
                break
            fo.write(chunk)
            if md5:
                h.update(chunk)
            if progress_callback is not None and size:
                n += len(chunk)
                progress_callback(n, size)
    fi.close()

    if md5 and h.hexdigest() != md5:
        raise MD5Mismatch("Error: received data MD5 sums mismatch")
    os.rename(path + '.part', path)


class FetchAPI(object):

    def __init__(self, remote, local_dir):
        self.remote = remote
        self.local_dir = local_dir

        self.action_callback = pprint_fn_action
        self.progress_callback = console_progress
        self.verbose = False

    def path(self, fn):
        return join(self.local_dir, fn)

    def fetch(self, key):
        self.action_callback(key, 'fetching')
        stream, info = self.remote.get(key)
        stream_to_file(stream, self.path(key), info, console_progress)

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

        self.action_callback(info['src'], 'patching')
        zdiff.patch(self.path(info['src']), self.path(egg),
                    self.path(patch_fn), self.progress_callback)
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
    import sys
    from optparse import OptionParser
    import enstaller.store.indexed as indexed
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
            sys.exit('Error: invalid egg name: %r' % fn)
        f.fetch_egg(fn, opts.force)


if __name__ == '__main__':
    main()
