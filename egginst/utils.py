import sys
import os
import shutil
from os.path import isdir, isfile, islink


on_win = bool(sys.platform == 'win32')

if on_win:
    bin_dir_name = 'Scripts'
    rel_site_packages = r'Lib\site-packages'
else:
    bin_dir_name = 'bin'
    rel_site_packages = 'lib/python%i.%i/site-packages' % sys.version_info[:2]


_cur = 0
def console_file_progress(so_far, total):
    """
    A progress callback to be used with write_data_from_url.

    Displays a progress bar as the download progresses.
    """
    if not total:
        return
    global _cur

    if so_far == 0:
        sys.stdout.write('%9s [' % human_bytes(total))
        sys.stdout.flush()
        _cur = 0

    if float(so_far) / total * 64 >= _cur:
        sys.stdout.write('.')
        sys.stdout.flush()
        _cur += 1

    if so_far == total:
        sys.stdout.write('.' * (65 - _cur))
        sys.stdout.write(']\n')
        sys.stdout.flush()


def pprint_fn_action(fn, action):
    """
    Pretty print the distribution name (filename) and an action, the width
    of the output corresponds to the with of the progress bar used by the
    function below.
    """
    print "%-56s %20s" % (fn, '[%s]' % action)


def rm_empty_dir(path):
    """
    Remove the directory `path` if it is a directory and empty.
    If the directory does not exist or is not empty, do nothing.
    """
    try:
        os.rmdir(path)
    except OSError: # directory might not exist or not be empty
        pass


def rm_rf(path, verbose=False):
    if not on_win and islink(path):
        # Note that we have to check if the destination is a link because
        # exists('/path/to/dead-link') will return False, although
        # islink('/path/to/dead-link') is True.
        if verbose:
            print "Removing: %r (link)" % path
        os.unlink(path)

    elif isfile(path):
        if verbose:
            print "Removing: %r (file)" % path
        if sys.platform == 'win32':
            try:
                os.unlink(path)
            except WindowsError:
                pass
        else:
            os.unlink(path)

    elif isdir(path):
        if verbose:
            print "Removing: %r (directory)" % path
        shutil.rmtree(path)


def human_bytes(n):
    """
    Return the number of bytes n in more human readable form.
    """
    if n < 1024:
        return '%i B' % n

    k = (n - 1) / 1024 + 1
    if k < 1024:
        return '%i KB' % k

    return '%.2f MB' % (float(n) / (2**20))
