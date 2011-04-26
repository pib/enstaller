import os
import sys
from collections import defaultdict
from os.path import basename, join, isdir, isfile



PATH = join(sys.prefix, 'registry.txt')

MODULE_EXTENSIONS = ('.pyd', '.so', '.py', '.pyw', '.pyc', 'pyo')
MODULE_EXTENSIONS_SET = set(MODULE_EXTENSIONS)


def read_file():
    if not isfile(PATH):
        return {}

    res = {}
    for line in open(PATH):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        k, v = line.split(None, 1)
        res[k] = v
    return res


def update_file(new_items):
    items = read_file()
    items.update(new_items)
    fo = open(PATH, 'w')
    for k, v in items.iteritems():
        fo.write('%s  %s\n' % (k, v))
    fo.close()


def create_hooks_dir(dir_path):
    res = {}
    modules = defaultdict(set)
    for fn in os.listdir(dir_path):
        if fn == 'EGG-INFO':
            continue

        path = join(dir_path, fn)
        if isdir(path):
            res[fn] = path

        elif isfile(path):
            name, ext = os.path.splitext(basename(path))
            if ext in MODULE_EXTENSIONS_SET:
                modules[name].add(ext)

    for name, exts in modules.iteritems():
        for mext in MODULE_EXTENSIONS:
            if mext in exts:
                res[name] = join(dir_path, name + mext)
                break

    return res


def create_hooks(egg):
    return create_hooks_dir(egg.pyloc)
