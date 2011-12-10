import sys
import os
import shutil
from os.path import isdir, isfile, islink, join
import logging


on_win = bool(sys.platform == 'win32')

if on_win:
    bin_dir_name = 'Scripts'
    rel_site_packages = r'Lib\site-packages'
else:
    bin_dir_name = 'bin'
    rel_site_packages = 'lib/python%i.%i/site-packages' % sys.version_info[:2]


class ProgressHandler(logging.Handler):
    usebytes = True

    def emit(self, record):
        if record.name == 'progress.start':
            d = record.msg
            self._tot = d['amount']
            self._cur = 0
            sys.stdout.write("%-56s %20s\n" % (d['filename'],
                                               '[%s]' % d['action']))
            sys.stdout.write('%9s [' % d['disp_amount'])
            sys.stdout.flush()
        elif record.name == 'progress.update':
            n = record.msg
            if 0 < n < self._tot and float(n) / self._tot * 64 > self._cur:
                sys.stdout.write('.')
                sys.stdout.flush()
                self._cur += 1
        elif record.name == 'progress.stop':
            sys.stdout.write('.' * (65 - self._cur))
            sys.stdout.write(']\n')
            sys.stdout.flush()

prog_logger = logging.getLogger('progress')
prog_logger.setLevel(logging.INFO)
prog_logger.addHandler(ProgressHandler())


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
        if on_win:
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


def get_executable(prefix):
    if on_win:
        path = join(prefix, 'python.exe')
        if isfile(path):
            return path
    else:
        path = join(prefix, bin_dir_name, 'python')
        if isfile(path):
            from subprocess import Popen, PIPE
            cmd = [path, '-c', 'import sys;print sys.executable']
            p = Popen(cmd, stdout=PIPE)
            return p.communicate()[0].strip()
    return sys.executable


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
