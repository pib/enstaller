import re
import os
from collections import defaultdict
from os.path import basename, join, isdir, isfile, normpath, splitext



MODULE_EXTENSIONS = ('.pyd', '.so', '.py', '.pyw', '.pyc', 'pyo')
MODULE_EXTENSIONS_SET = set(MODULE_EXTENSIONS)


def stripped_lines(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line


def is_namespace(dir_path):
    modules = set()
    for fn in os.listdir(dir_path):
        path = join(dir_path, fn)
        if isfile(path):
            name, ext = splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules.add(name)
    return modules == set(['__init__'])


id_pat = re.compile(r'[a-zA-Z_]\w*$')
def create_hooks_dir(dir_path, namespace=''):
    reg = {}
    modules = defaultdict(set)
    pth = []
    for fn in os.listdir(dir_path):
        name, ext = splitext(fn)
        if not id_pat.match(name):
            continue

        path = join(dir_path, fn)
        if isdir(path) and ext == '':
            reg[namespace + fn] = path
            if is_namespace(path):
                add_reg, dummy = create_hooks_dir(path, namespace + fn + '.')
                reg.update(add_reg)

        elif isfile(path):
            if ext in MODULE_EXTENSIONS_SET:
                modules[name].add(ext)

            elif ext == '.pth':
                for line in stripped_lines(path):
                    pth.append(normpath(join(dir_path, line)))

    for name, exts in modules.iteritems():
        if name == '__init__':
            continue
        for mext in MODULE_EXTENSIONS:
            if mext in exts:
                reg[namespace + name] = join(dir_path, name + mext)
                break

    return reg, pth


def create_file(egg):
    reg, pth = create_hooks_dir(egg.pkg_dir)
    def mk_rel(p):
        p = p.replace(egg.pkg_dir, '..').replace('\\', '/')
        if p == '..':
            return '../.'
        return p

    fo = open(egg.registry_txt, 'w')
    fo.write('# pkg: %s\n' % basename(egg.pkg_dir))
    for k, p in reg.iteritems():
        fo.write('%s  %s\n' % (k, mk_rel(p)))
    for p in pth:
        fo.write('-pth-  %s\n' % mk_rel(p))
    fo.close()


REGISTRY_CODE = """\
import sys
import imp
from os.path import abspath, dirname, join, splitext

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


def update_registry(paths):
    registry = {}
    for path in paths:
        for line in open(path):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            k, v = line.split(None, 1)
            p = abspath(join(dirname(path), v))
            if k == '-pth-':
                if v not in sys.path:
                    sys.path.insert(0, p)
            else:
                registry[k] = p
    sys.meta_path.insert(0, PackageRegistry(registry))
"""
