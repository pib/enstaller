import bz2
import os
import re
import sys
import time
import hashlib
import logging
from cStringIO import StringIO
from os.path import abspath, expanduser, getmtime, getsize, isfile, join

from egginst import name_version_fn
from enstaller.verlib import NormalizedVersion, IrrationalVersionError

logger = logging.getLogger(__name__)

PY_VER = '%i.%i' % sys.version_info[:2]


def abs_expanduser(path):
    return abspath(expanduser(path))


def canonical(s):
    """
    return the canonical representations of a project name
    """
    # eventually (once Python 2.6 repo eggs are no longer supported), this
    # function should only return s.lower()
    s = s.lower()
    s = s.replace('-', '_')
    if s == 'tables':
        s = 'pytables'
    return s


def cname_fn(fn):
    return canonical(fn.split('-')[0])


def comparable_version(version):
    """
    Given a version string (e.g. '1.3.0.dev234'), return an object which
    allows correct comparison. For example:
        comparable_version('1.3.10') > comparable_version('1.3.8')  # True
    whereas:
        '1.3.10' > '1.3.8'  # False
    """
    try:
        # This hack makes it possible to use 'rc' in the version, where
        # 'rc' must be followed by a single digit.
        ver = version.replace('rc', '.dev99999')
        return NormalizedVersion(ver)
    except IrrationalVersionError:
        # If obtaining the RationalVersion object fails (for example for
        # the version '2009j'), simply return the string, such that
        # a string comparison can be made.
        return version


def md5_file(path):
    """
    Returns the md5sum of the file (located at `path`) as a hexadecimal
    string of length 32.
    """
    fi = open(path, 'rb')
    h = hashlib.new('md5')
    while True:
        chunk = fi.read(65536)
        if not chunk:
            break
        h.update(chunk)
    fi.close()
    return h.hexdigest()


def info_file(path):
    return dict(
        size=getsize(path),
        mtime=getmtime(path),
        md5=md5_file(path),
    )


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
        sys.exit("Error: received data MD5 sums mismatch")
    os.rename(path + '.part', path)

# -----------------------------------------------------------------

repo_pat = re.compile(r'/repo/([^\s/]+/[^\s/]+)/')
def shorten_repo(repo):
    m = repo_pat.search(repo)
    if m:
        return m.group(1)
    else:
        res = repo.replace('http://', '').replace('https://', '')
        return res.replace('.enthought.com', '')


def get_installed_info(prefix, cname):
    """
    return a dictionary with information about the package specified by the
    canonical name found in prefix, or None if the package is not found
    """
    meta_dir = join(prefix, 'EGG-INFO', cname)
    meta_txt = join(meta_dir, '__egginst__.txt')
    if not isfile(meta_txt):
        return None

    d = {}
    execfile(meta_txt, d)
    res = {}
    res['egg_name'] = d['egg_name']
    res['name'], res['version'] = name_version_fn(d['egg_name'])
    res['mtime'] = time.ctime(getmtime(meta_txt))
    res['meta_dir'] = meta_dir

    meta2_txt = join(meta_dir, '__enpkg__.txt')
    if isfile(meta2_txt):
        d = {}
        execfile(meta2_txt, d)
        res['repo'] = shorten_repo(d['repo'])
    return res
