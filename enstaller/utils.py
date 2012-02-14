import sys
import hashlib
from os.path import abspath, expanduser, getmtime, getsize, isdir

from verlib import NormalizedVersion, IrrationalVersionError


PY_VER = '%i.%i' % sys.version_info[:2]


def abs_expanduser(path):
    return abspath(expanduser(path))


def canonical(s):
    """
    return the canonical representations of a project name
    DON'T USE THIS IN NEW CODE (ONLY (STILL) HERE FOR HISTORICAL REASONS)
    """
    # eventually (once Python 2.6 repo eggs are no longer supported), this
    # function should only return s.lower()
    s = s.lower()
    s = s.replace('-', '_')
    if s == 'tables':
        s = 'pytables'
    return s


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
    return dict(size=getsize(path),
                mtime=getmtime(path),
                md5=md5_file(path))


def cleanup_url(url):
    """
    Ensure a given repo string, i.e. a string specifying a repository,
    is valid and return a cleaned up version of the string.
    """
    if url.startswith(('http://', 'https://')):
        if not url.endswith('/'):
            url += '/'

    elif url.startswith('file://'):
        dir_path = url[7:]
        if dir_path.startswith('/'):
            # Unix filename
            if not url.endswith('/'):
                url += '/'
        else:
            # Windows filename
            if not url.endswith('\\'):
                url += '\\'

    elif isdir(abs_expanduser(url)):
        return cleanup_url('file://' + abs_expanduser(url))

    else:
        raise Exception("Invalid URL or non-existing file: %r" % url)

    return url


def fill_url(url):
    import plat

    url = url.replace('{ARCH}', plat.arch)
    url = url.replace('{SUBDIR}', plat.subdir)
    return cleanup_url(url)
