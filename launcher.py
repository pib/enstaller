import os
import sys
import subprocess
import shutil
import tempfile
import urllib2
import zipfile
from os.path import dirname, isdir, isfile, join
from optparse import OptionParser


verbose = False
pkgs_dir = None
prefix = None
python_exe = None
repo_url = None
local_repo = None


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


def download(url, path):
    """
    download a file from the url to path
    """
    print 'Downloading: %r' % url
    print '         to: %r' % path
    fi = urllib2.urlopen(url)
    if not isdir(dirname(path)):
        os.makedirs(dirname(path))
    fo = open(path, 'wb')
    fo.write(fi.read())
    fo.close()
    fi.close()


def fetch_file(fn, force=False):
    path = join(local_repo, fn)
    if not isfile(path) or force:
        if not isdir(local_repo):
            os.makedirs(local_repo)
        download(repo_url + fn, path)
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


def bootstrap_enstaller(pkg):
    assert pkg.startswith('enstaller-')
    code = ("import sys;"
            "sys.path.insert(0, %r);"
            "from egginst.bootstrap import main;"
            "main(hook=True, pkgs_dir=%r)" % (
                     fetch_file(pkg + '.egg'), pkgs_dir))
    subprocess.check_call([python_exe, '-c', code])


def update_pkgs(pkgs):
    if not isfile(python_exe):
        unzip(fetch_file(pkgs[0] + '.egg'), prefix)

    if not isfile(registry_pkg(pkgs[1])):
        bootstrap_enstaller(pkgs[1])

    if not isfile(registry_pkg(pkgs[2])): # bsdiff4
        launch(pkgs[1:2], 'egginst.main:main',
               ['--hook', join(local_repo, fetch_file(pkgs[2] + '.egg')),
                '--pkgs-dir', pkgs_dir])

    eggs_to_fetch = []
    for pkg in pkgs[3:]:
        if isfile(registry_pkg(pkg)):
            continue
        egg_name = pkg + '.egg'
        if not isfile(join(local_repo, egg_name)):
            eggs_to_fetch.append(egg_name)

    if eggs_to_fetch:
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

    if len(args) != 1:
        p.error('exactly one argument expected, try -h')

    global verbose, prefix, pkgs_dir, python_exe, local_repo, repo_url
    verbose = opts.verbose

    if opts.env:
        pkgs = parse_env_file(opts.env)
    else:
        pkgs = ['Python-2.6.6-1', 'enstaller-4.5.0-1', 'bsdiff4-1.0.1-2']

    assert pkgs[0].startswith('Python-')
    assert pkgs[1].startswith('enstaller-')
    assert pkgs[2].startswith('bsdiff4-')

    root_dir = r'C:\jpm'
    local_repo = join(root_dir, 'repo')
    prefix = join(root_dir, pkgs[0])
    pkgs_dir = join(prefix, 'pkgs')
    python_exe = join(prefix, 'python.exe')
    repo_url = 'http://www.enthought.com/repo/.jpm/Windows/x86/'

    update_pkgs(pkgs)
    return launch(pkgs[1:], entry_pt=args[0], args=opts.args.split())


if __name__ == '__main__':
    sys.exit(main())
