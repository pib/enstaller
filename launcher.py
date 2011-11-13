import os
import sys
import subprocess
import shutil
import tempfile
import urllib2
import zipfile
from os.path import basename, isdir, join
from optparse import OptionParser


verbose = False
pkgs_dir = None
python_exe = None


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
        pkgs.append(line)
    return pkgs


def parse_registry_files(pkgs):
    pth = []
    registry = {}
    for pkg in pkgs:
        reg_path = join(pkgs_dir, pkg, 'EGG-INFO', 'registry.txt')
        for line in yield_lines(reg_path):
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
        shutil.rmtree(tmp_dir)
    return exit_code


def bootstrap_enstaller(egg_path):
    assert basename(egg_path).startswith('enstaller-')
    code = ("import sys; "
            "sys.path.insert(0, %r); "
            "from egginst.bootstrap import main; "
            "main(hook=True)" % egg_path)
    subprocess.call([python_exe, '-c', code])


def install_pkg(pkg):
    enstaller = 'enstaller-4.5.0-1'
    local_repo = join(sys.prefix, 'LOCAL-REPO')
    if not isdir(join(pkgs_dir, enstaller)):
        bootstrap_enstaller(join(local_repo, 'enstaller-4.5.0-1.egg'))
    launch([enstaller], 'egginst.main:main',
           ['--hook', join(local_repo, pkg + '.egg')])


def update_pkgs(pkgs):
    for pkg in pkgs:
        if isdir(join(pkgs_dir, pkg)):
            continue
        install_pkg(pkg)


def main():
    p = OptionParser(usage="usage: %prog [options] ENTRY",
                     description=__doc__)

    p.add_option("--args",
                 action="store",
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

    global verbose, pkgs_dir, python_exe
    verbose = opts.verbose
    pkgs_dir = '/Library/Frameworks/Python.framework/Versions/7.1/pkgs'
    python_exe = 'python'

    if opts.env:
        pkgs = parse_env_file(opts.env)
    else:
        pkgs = []

    update_pkgs(pkgs)
    return launch(pkgs,
                  entry_pt=args[0],
                  args=opts.args.split() if opts.args else [])


if __name__ == '__main__':
    sys.exit(main())
    #create_entry('foo.py',
    #             '/Library/Frameworks/Python.framework/Versions/7.1/pkgs',
    #             ['nose-1.1.2-1', 'numpy-1.5.1-2'],
    #             'nose:run_exit')
    #       ['--version'])
