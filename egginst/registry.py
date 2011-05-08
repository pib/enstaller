import os
import sys
from collections import defaultdict
from os.path import basename, join, isdir, isfile, normpath



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
                add_reg, dummy = create_hooks_dir(path, namespace + fn + '.')
                reg.update(add_reg)

        elif isfile(path):
            name, ext = os.path.splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules[name].add(ext)

            if ext == '.pth':
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

    fo = open(egg.registry_txt, 'w')
    fo.write('# pkg: %s\n' % basename(egg.pkg_dir))
    for kv in reg.iteritems():
        fo.write('%s  %s\n' % kv)
    for p in pth:
        fo.write('-pth-  %s\n' % p)
    fo.close()


def collect(packages, path):
    """
    collects the EGG-INFO/registry.txt files for `packages` and writes them
    to a single registry file at `path`
    """
    fo = open(path, 'w')
    for pkg in packages:
        path = join(sys.prefix, 'pkgs', pkg, 'EGG-INFO', 'registry.txt')
        fo.write(open(path).read())
    fo.close()
