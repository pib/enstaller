import os
import sys
import hashlib
import subprocess
import shutil
import tempfile
import urllib2
import urlparse
import zipfile
from cStringIO import StringIO
from os.path import dirname, isdir, isfile, join
from optparse import OptionParser


verbose = False
pkgs_dir = None
prefix = None
python_exe = None
local_repo = None
if sys.platform == 'win32':
    repo_url = 'http://www.enthought.com/repo/.jpm/Windows/x86/'
elif sys.platform == 'darwin':
    repo_url = 'file:///Users/ischnell/repo/'


def human_bytes(n):
    """
    return the number of bytes n in more human readable form
    """
    if n < 1024:
        return '%i B' % n
    k = (n - 1) / 1024 + 1
    if k < 1024:
        return '%i KB' % k
    return '%.2f MB' % (float(n) / (2**20))


def console_progress(so_far, total, usebytes=True, state={}):
    """
    progress callback
    """
    if so_far == 0:
        sys.stdout.write('%9s [' %
                         (human_bytes(total) if usebytes else total))
        sys.stdout.flush()
        state['cur'] = 0
    if float(so_far) / total * 64 >= state['cur']:
        sys.stdout.write('.')
        sys.stdout.flush()
        state['cur'] += 1
    if so_far == total:
        sys.stdout.write('.' * (65 - state['cur']))
        sys.stdout.write(']\n')
        sys.stdout.flush()


userpass = None  # a tuple of username and password
def open_with_auth(url):
    """
    open a urllib2 request, handling HTTP authentication
    """
    scheme, netloc, path, params, query, frag = urlparse.urlparse(url)
    auth, host = urllib2.splituser(netloc)
    if auth:
        auth = urllib2.unquote(auth).encode('base64').strip()
    elif userpass:
        auth = ('%s:%s' % userpass).encode('base64')

    if auth:
        new_url = urlparse.urlunparse((scheme, host, path,
                                       params, query, frag))
        request = urllib2.Request(new_url)
        request.add_unredirected_header("Authorization", "Basic " + auth)
    else:
        request = urllib2.Request(url)
    request.add_header('User-Agent', 'enstaller')
    return urllib2.urlopen(request)


def write_data_from_url(fo, url, md5=None, size=None, progress_callback=None):
    """
    Read data from the url and write to the file handle fo, which must
    be open for writing.  Optionally check the MD5.  When the size in
    bytes and progress_callback are provided, the callback is called
    with progress updates as the download/copy occurs.  If no size is
    provided, the callback is not called.

    The callback will be called with 0% progress at the beginning and
    100% progress at the end, so these two states can be used for any
    initial and final display.
    """
    if progress_callback is not None and size:
        n = 0
        progress_callback(0, size)

    if url.startswith('file://'):
        path = url[7:]
        fi = open(path, 'rb')
    elif url.startswith(('http://', 'https://')):
        fi = open_with_auth(url)
    else:
        raise Exception("Error: cannot handle url: %r" % url)

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
        if progress_callback is not None and size:
            n += len(chunk)
            progress_callback(n, size)

    fi.close()

    if md5 and h.hexdigest() != md5:
        sys.stderr.write("FATAL ERROR: Data received from\n"
                         "    %s\n"
                         "is corrupted.  MD5 sums mismatch.\n" % url)
        fo.close()
        sys.exit(1)


def fetch_file(url, path):
    """
    fetch a file from 'url' and write it to 'path'
    """
    print 'Fetching: %r' % url
    print '      to: %r' % path
    if not isdir(dirname(path)):
        os.makedirs(dirname(path))
    fo = open(path, 'wb')
    write_data_from_url(fo, url, progress_callback=console_progress)
    fo.close()


def fetch_data(url):
    """
    fetch data from 'url' and return the data as a string
    """
    faux = StringIO()
    write_data_from_url(faux, url)
    data = faux.getvalue()
    faux.close()
    return data


def read_app_index():
    data = fetch_data(repo_url + 'index-app.json')
    index = eval(data)
    app = index["test-1.0-1.egg"]
    return app


def fetch_to_repo(fn, force=False):
    path = join(local_repo, fn)
    if not isfile(path) or force:
        fetch_file(repo_url + fn, path)
    return path


def registry_pkg(pkg):
    return join(pkgs_dir, pkg, 'EGG-INFO', 'registry.txt')


def yield_lines(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line


def parse_env_file(path):
    pkgs = []
    for line in yield_lines(path):
        if line.endswith('.egg'):
            line = line[:-4]
        assert line.count('-') == 2
        pkgs.append(line)
    return pkgs


def parse_registry_files(pkgs):
    pth = []
    registry = {}
    for pkg in pkgs:
        for line in yield_lines(registry_pkg(pkg)):
            k, v = line.split(None, 1)
            if k == '-pth-':
                if v not in pth:
                    pth.append(v)
            else:
                registry[k] = v
    return pth, registry


def create_entry(dst_path, pkgs, entry_pt):
    """
    create entry point Python script at 'dst_path', which sets up registry
    for the packages 'pkgs' (list) and entry point 'entry_pt' (something
    like 'package.module:function')
    """
    fo = open(dst_path, 'w')
    fo.write("""\
import sys
import imp
from os.path import splitext

EXT_INFO_MAP = {
    '.py': ('.py', 'U', imp.PY_SOURCE),
    '.pyw': ('.pyw', 'U', imp.PY_SOURCE),
    '.pyc': ('.pyc', 'rb', imp.PY_COMPILED),
    '.pyo': ('.pyo', 'rb', imp.PY_COMPILED),
    '.pyd': ('.pyd', 'rb', imp.C_EXTENSION),
    '.so': ('.so', 'rb', imp.C_EXTENSION),
    '': ('', '', imp.PKG_DIRECTORY),
}

class PackageRegistry(object):
    def __init__(self, registry={}):
        self.registry = registry
        self._path = None

    def find_module(self, fullname, path=None):
        try:
            self._path = self.registry[fullname]
            return self
        except KeyError:
            return None

    def load_module(self, fullname):
        mod = sys.modules.get(fullname)
        if mod:
            return mod
        assert self._path, "_path=%r" % self._path
        info = EXT_INFO_MAP[splitext(self._path)[-1]]
        if info[1]:
            f = open(self._path, info[1])
        else:
            f = None
        try:
            mod = imp.load_module(fullname, f, self._path, info)
        finally:
            if f is not None:
                f.close()
        return mod
""")

    pth, registry = parse_registry_files(pkgs)
    fo.write("""
if __name__ == '__main__':
    for p in %r:
        if p not in sys.path:
            sys.path.insert(0, p)
    sys.meta_path.insert(0, PackageRegistry({
""" % pth)
    for k in sorted(registry.keys()):
        fo.write('%r: %r,\n' % (k, registry[k]))
    fo.write("    }))\n")

    if entry_pt.count(':') == 0:
        entry_pt += ':main'
    assert entry_pt.count(':') == 1
    module, func = entry_pt.strip().split(':')
    fo.write("""
    from %(module)s import %(func)s
    sys.exit(%(func)s())
""" % locals())
    fo.close()


def launch(pkgs, entry_pt, args=None):
    if args is None:
        args = []
    tmp_dir = tempfile.mkdtemp()
    try:
        path = join(tmp_dir, 'entry.py')
        create_entry(path, pkgs, entry_pt)
        exit_code = subprocess.call([python_exe, path] + args)
    finally:
        try:
            shutil.rmtree(tmp_dir)
        except:
            pass
    return exit_code


def unzip(zip_path, dir_path):
    """
    unpack the zip file into dir_path, creating directories as required
    """
    print "Unzipping: %r" % zip_path
    print "     into: %r" % dir_path
    z = zipfile.ZipFile(zip_path)
    for name in z.namelist():
        if name.endswith('/') or name.startswith('.unused'):
            continue
        path = join(dir_path, *name.split('/'))
        dpath = dirname(path)
        if not isdir(dpath):
            os.makedirs(dpath)
        fo = open(path, 'wb')
        fo.write(z.read(name))
        fo.close()
    z.close()


def bootstrap_enstaller(pkg):
    assert pkg.startswith('enstaller-')
    code = ("import sys;"
            "sys.path.insert(0, %r);"
            "from egginst.bootstrap import main;"
            "main(hook=True, pkgs_dir=%r)" % (
                     fetch_to_repo(pkg + '.egg'), pkgs_dir))
    subprocess.check_call([python_exe, '-c', code])


def update_pkgs(pkgs):
    if not isfile(python_exe):
        unzip(fetch_to_repo(pkgs[0] + '.egg'), prefix)

    if not isfile(registry_pkg(pkgs[1])):
        bootstrap_enstaller(pkgs[1])

    if not isfile(registry_pkg(pkgs[2])): # bsdiff4
        launch(pkgs[1:2], 'egginst.main:main',
               ['--hook', join(local_repo, fetch_to_repo(pkgs[2] + '.egg')),
                '--pkgs-dir', pkgs_dir])

    eggs_to_fetch = []
    for pkg in pkgs[3:]:
        if isfile(registry_pkg(pkg)):
            continue
        egg_name = pkg + '.egg'
        if not isfile(join(local_repo, egg_name)):
            eggs_to_fetch.append(egg_name)

    if eggs_to_fetch:
        if not isdir(local_repo):
            os.makedirs(local_repo)
        args = ['--dst', local_repo, repo_url] + eggs_to_fetch
        if launch(pkgs[1:3], 'enstaller.indexed_repo.chain:main', args):
            sys.exit('Error: could not fetch %r' % args)

    for pkg in pkgs[1:]:
        if isfile(registry_pkg(pkg)):
            continue
        launch(pkgs[1:3], 'egginst.main:main',
               ['--hook', join(local_repo, pkg + '.egg'),
                '--pkgs-dir', pkgs_dir])


def main():
    p = OptionParser(usage="usage: %prog [options] ENTRY",
                     description=__doc__)

    p.add_option("--args",
                 action="store",
                 default='',
                 help="additional arguments passed to the launched command")
    p.add_option("--env",
                 action="store",
                 help="Python environment file(s), separated by ';'",
                 metavar='PATH')
    p.add_option('-v', "--verbose", action="store_true")
    #p.add_option('--version', action="store_true")

    opts, args = p.parse_args()

    global verbose, prefix, pkgs_dir, python_exe, local_repo, repo_url
    verbose = opts.verbose

    pkgs = ['Python-2.6.6-1', 'enstaller-4.5.0-1', 'bsdiff4-1.0.1-2']
    if len(args) == 0:
        app = read_app_index()
        entry, pkgs = app['entry'], app['pkgs']
    elif len(args) == 1:
        entry = args[0]
    else:
        p.error('not more than one argument expected, try -h')

    if opts.env:
        pkgs = parse_env_file(opts.env)

    if verbose:
        print "entry = %r" % entry
        print "pkgs = %r" % pkgs

    assert pkgs[0].startswith('Python-')
    assert pkgs[1].startswith('enstaller-')
    assert pkgs[2].startswith('bsdiff4-')

    if sys.platform == 'win32':
        root_dir = r'C:\jpm'
    elif sys.platform == 'darwin':
        root_dir = '/Users/ischnell/jpm'
    local_repo = join(root_dir, 'repo')
    prefix = join(root_dir, pkgs[0])
    pkgs_dir = join(prefix, 'pkgs')
    if sys.platform == 'win32':
        python_exe = join(prefix, 'python.exe')
    else:
        python_exe = join(prefix, 'bin', 'python')

    update_pkgs(pkgs)
    return launch(pkgs[1:], entry_pt=entry, args=opts.args.split())


if __name__ == '__main__':
    sys.exit(main())
