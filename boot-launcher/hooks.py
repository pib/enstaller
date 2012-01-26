import os
import sys
import imp
from os.path import isfile, join, splitext


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
        """
        Find fullname in the registry if it is recorded directly or if any
        of the partial names are recorded.
        That is, if there is a registry entry for scipy.stats then
        scipy.stats.distributions will be found underneath the path tree
        where it is located.
        """
        # sys.stderr.write("# registry find_module: %s (path=%s)\n" %
        #                  (fullname, path))
        try:
            self._path = self.registry[fullname]
            return self
        except KeyError:
            return None

    def load_module(self, fullname):
        """
        uses imp.load_module
        """
        # print "Called load_module", fullname
        mod = sys.modules.get(fullname)
        if mod:
            return mod

        if sys.flags.verbose:
            sys.stderr.write("# registry load_module: %s\n" % fullname)
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


def update(path):
    """
    updates the registry and sys.path given the path to a registry file

    The registry file should have one entry per package and additional
    entries for any individual files that don't fit under any package
    (essentially) anything that is top level.
    In addition, it may contain "-pth-" entries, which are simply appended
    to sys.path.
    """
    registry = {}
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, v = line.split(None, 1)
        if k == '-pth-':
            if v not in sys.path:
                sys.path.insert(0, v)
        else:
            registry[k] = v

    sys.meta_path.insert(0, PackageRegistry(registry))


def main():
    """
    called from main() in site.py
    """
    path = os.environ.get('EPDREGISTRY', join(sys.prefix, 'registry.txt'))
    if sys.flags.verbose:
        sys.stderr.write("# registry file: %s\n" % path)

    if isfile(path):
        update(path)
    elif sys.flags.verbose:
        sys.stderr.write("# WARNING: registry file does not exist\n")


if __name__ == '__main__':
    main()
