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


def is_namespace(dir_path):
    modules = set()
    for fn in os.listdir(dir_path):
        path = join(dir_path, fn)
        if isfile(path):
            name, ext = os.path.splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules.add(name)

    return modules == set(['__init__'])


def create_hooks_dir(dir_path, namespace=''):
    reg = {}
    modules = defaultdict(set)
    pth = []
    for fn in os.listdir(dir_path):
        if '-' in fn:
            continue

        path = join(dir_path, fn)
        if isdir(path):
            reg[namespace + fn] = path
            if is_namespace(path):
                add_reg, dummy = create_hooks_dir(path, fn + '.')
                reg.update(add_reg)

        elif isfile(path):
            name, ext = os.path.splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules[name].add(ext)

            if ext == '.pth':
                for line in stripped_lines(path):
                    pth.append(abspath(join(dir_path, line)))

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

    fo = open(join(egg.pkg_dir, 'EGG-INFO', 'registry.txt'), 'w')
    fo.write('# pkg: %s\n' % basename(egg.pkg_dir))
    for kv in reg.iteritems():
        fo.write('%s  %s\n' % kv)
    for p in pth:
        fo.write('-pth-  %s\n' % p)
    fo.close()
