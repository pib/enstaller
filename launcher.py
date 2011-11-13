import os
import subprocess
import shutil
import tempfile
import urllib2
import zipfile
from os.path import join
from optparse import OptionParser


verbose = False


def read_registry_files(pkgs_dir, pkgs):
    pth = []
    registry = {}
    for pkg in pkgs:
        for line in open(join(pkgs_dir, pkg, 'EGG-INFO', 'registry.txt')):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            k, v = line.split(None, 1)
            if k == '-pth-':
                if v not in pth:
                    pth.append(v)
            else:
                registry[k] = v
    return pth, registry


def create_entry(dst_path, pkgs_dir, pkgs, entry_pt):
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

    pth, registry = read_registry_files(pkgs_dir, pkgs)
    module, func = entry_pt.strip().split(':')
    fo.write("""\
if __name__ == '__main__':
    for p in %r:
        if p not in sys.path:
            sys.path.insert(0, p)
    sys.meta_path.insert(0, PackageRegistry({
""" % pth)
    for k in sorted(registry.keys()):
        fo.write('%r: %r,\n' % (k, registry[k]))

    if entry_pt.count(':') == 0:
        entry_pt += ':main'
    assert entry_pt.count(':') == 1
    fo.write("""\
    }))

    from %(module)s import %(func)s
    sys.exit(%(func)s())
""" % locals())
    fo.close()


def launch(pkgs_dir, pkgs, entry_pt):
    tmp_dir = tempfile.mkdtemp()
    print "TMP DIR: %r" % tmp_dir
    try:
        path = join(tmp_dir, 'entry.py')
        create_entry(path, pkgs_dir, pkgs, entry_pt)
        exit_code = subprocess.call(['python', path])
    finally:
        shutil.rmtree(tmp_dir)
    return exit_code


def main():
    p = OptionParser(usage="usage: %prog [options] PYTHON_SCRIPT",
                     description=__doc__)

    p.add_option("--env",
                 action="store",
                 help="Python environment file(s), separated by ';'",
                 metavar='PATH')

    p.add_option('-v', "--verbose", action="store_true")
    p.add_option('--version', action="store_true")

    opts, args = p.parse_args()

    global verbose
    verbose = opts.verbose


if __name__ == '__main__':
    #main()
#    create_entry('foo.py',
    launch('/Library/Frameworks/Python.framework/Versions/7.1/pkgs',
           ['nose-1.1.2-1', 'numpy-1.5.1-2'],
           'nose:run_exit')
