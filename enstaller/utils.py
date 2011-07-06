import bz2
import re
import sys
import time
import hashlib
import urlparse
import urllib2
from cStringIO import StringIO
from os.path import abspath, expanduser, getmtime, isfile, join

from egginst import name_version_fn
from egginst.utils import human_bytes
from enstaller import __version__
from enstaller.verlib import NormalizedVersion, IrrationalVersionError


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


def open_with_auth(url):
    """
    Open a urllib2 request, handling HTTP authentication
    """
    import config

    scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
    assert not query
    auth, host = urllib2.splituser(netloc)
    if auth:
        auth = urllib2.unquote(auth).encode('base64').strip()
    elif 'enthought.com/repo/' in url and 'repo/pypi/eggs/' not in url:
        auth = config.get('EPD_auth')
        if auth is None:
            userpass = config.get('EPD_userpass')
            if userpass:
                auth = userpass.encode('base64').strip()

    if auth:
        new_url = urlparse.urlunparse((scheme, host, path,
                                       params, query, frag))
        request = urllib2.Request(new_url)
        request.add_header("Authorization", "Basic " + auth)
    else:
        request = urllib2.Request(url)
    request.add_header('User-Agent', 'enstaller/%s' % __version__)
    try:
        return urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        sys.stderr.write(str(e) + '\n')
        if '401' in str(e):
            sys.stderr.write("""\
Please make sure you are using the correct authentication.
Use "enpkg --userpass" to update authentication in configuration file.
""")
        sys.exit(1)


def write_data_from_url(fo, url, md5=None, size=None):
    """
    Read data from the url and write to the file handle fo, which must be
    open for writing.  Optionally check the MD5.  When the size in bytes
    is provided, a progress bar is displayed using the download/copy.
    """
    if size:
        sys.stdout.write('%9s [' % human_bytes(size))
        sys.stdout.flush()
        n = cur = 0

    if url.startswith('file://'):
        path = url[7:]
        fi = open(path, 'rb')
    elif url.startswith(('http://', 'https://')):
        try:
            fi = open_with_auth(url)
        except urllib2.URLError, e:
            sys.exit("%s %s" % (e, url))
    else:
        sys.exit("Error: invalid url: %r" % url)

    h = hashlib.new('md5')

    if size and size < 16384:
        buffsize = 1
    else:
        buffsize = 256

    while True:
        chunk = fi.read(buffsize)
        if not chunk:
            break
        fo.write(chunk)
        if md5:
            h.update(chunk)
        if not size:
            continue
        n += len(chunk)
        if float(n) / size * 64 >= cur:
            sys.stdout.write('.')
            sys.stdout.flush()
            cur += 1

    if size:
        sys.stdout.write(']\n')
        sys.stdout.flush()

    fi.close()

    if md5 and h.hexdigest() != md5:
        sys.stderr.write("FATAL ERROR: Data received from\n\n"
                         "    %s\n\n"
                         "is corrupted.  MD5 sums mismatch.\n" % url)
        fo.close()
        sys.exit(1)

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


def get_info():
    """
    returns a dict mapping canonical project names to spec structures
    containing additional meta-data of the project which is not contained
    in the index-depend data
    """
    from indexed_repo.metadata import parse_index
    import config

    url = config.get('info_url')
    faux = StringIO()
    write_data_from_url(faux, url)
    index_data = faux.getvalue()
    faux.close()

    if url.endswith('.bz2'):
        index_data = bz2.decompress(index_data)

    res = {}
    for name, data in parse_index(index_data).iteritems():
        d = {}
        exec data.replace('\r', '') in d
        cname = canonical(name)
        res[cname] = {}
        for var_name in ('name', 'homepage', 'doclink', 'license',
                         'summary', 'description'):
            res[cname][var_name] = d[var_name]
    return res


def get_available():
    """
    return a dict mapping canonical project names to versions which
    are available in the subscriber repositories
    """
    import plat
    import config

    url = '%savailable/%s.txt' % (config.pypi_url, plat.custom_plat)
    faux = StringIO()
    write_data_from_url(faux, url)
    data = faux.getvalue()
    faux.close()

    res = {}
    for line in data.splitlines():
        line = line.strip()
        if line:
            parts = line.split()
            cname = parts[0]
            versions = parts[1:]
            res[cname] = versions
    return res
