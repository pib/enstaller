import sys
from os.path import join, isfile



PATH = join(sys.prefix, 'registry.txt')

MODULE_EXTENSIONS = ('.pyd', '.so', '.py', '.pyw', '.pyc', 'pyo')
MODULE_EXTENSIONS_SET = set(MODULE_EXTENSIONS)


def read_file():
    res = {}
    if not isfile(PATH):
        return res
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
