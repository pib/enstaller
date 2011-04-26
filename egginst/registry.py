import os
import sys
from collections import defaultdict
from os.path import abspath, basename, join, isdir, isfile



PATH = join(sys.prefix, 'registry.txt')

MODULE_EXTENSIONS = ('.pyd', '.so', '.py', '.pyw', '.pyc', 'pyo')
MODULE_EXTENSIONS_SET = set(MODULE_EXTENSIONS)


def stripped_lines(path):
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        yield line


def read_file():
    if not isfile(PATH):
        return {}
    res = {}
    for line in stripped_lines(PATH):
        k, v = line.split(None, 1)
        res[k] = v
    return res


def create_hooks_dir(dir_path):
    reg = {}
    modules = defaultdict(set)
    pth = []
    for fn in os.listdir(dir_path):
        if fn == 'EGG-INFO':
            continue

        path = join(dir_path, fn)
        if isdir(path):
            reg[fn] = path

        elif isfile(path):
            name, ext = os.path.splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules[name].add(ext)

            if ext == '.pth':
                for line in stripped_lines(path):
                    pth.append(abspath(join(dir_path, line)))

    for name, exts in modules.iteritems():
        for mext in MODULE_EXTENSIONS:
            if mext in exts:
                reg[name] = join(dir_path, name + mext)
                break

    return reg, pth


def create_file(egg):
    reg, pth = create_hooks_dir(egg.pkg_dir)

    fo = open(join(egg.pkg_dir, 'EGG-INFO', 'registry.txt'), 'w')
    fo.write('# pkg: %s\n' % basename(egg.pkg_dir))
    for kv in reg.iteritems():
        fo.write('%s  %s\n' % kv)
    for p in pth:
        fo.write('-pth-  %s\n' % p)
    fo.close()
