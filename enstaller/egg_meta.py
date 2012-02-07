import re
import os
import json
import zipfile
from os.path import getmtime, isfile, join

from egginst.eggmeta import info_from_z

from utils import info_file


egg_fmt = '%(name)s-%(version)s-%(build)d.egg'

egg_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)\.egg$')

def is_valid_eggname(eggname):
    return bool(egg_pat.match(eggname))

def split_eggname(eggname):
    m = egg_pat.match(eggname)
    assert m, eggname
    return m.group(1), m.group(2), int(m.group(3))

def info_from_egg(path):
    z = zipfile.ZipFile(path)
    res = info_from_z(z)
    z.close()
    return res

def update_index(dir_path, force=False, verbose=False):
    index_path = join(dir_path, 'index.json')
    if force or not isfile(index_path):
        index = {}
    else:
        index = json.load(open(index_path, 'r'))

    new_index = {}
    for fn in os.listdir(dir_path):
        if not is_valid_eggname(fn):
            continue
        path = join(dir_path, fn)
        info = index.get(fn)
        if info and getmtime(path) == info['mtime']:
            new_index[fn] = info
            continue
        info = info_file(path)
        info.update(info_from_egg(path))
        new_index[fn] = info

    patches_index_path = join(dir_path, 'patches', 'index.json')
    if isfile(patches_index_path):
        patch_index = json.load(open(patches_index_path))
        for info in patch_index.itervalues():
            info['type'] = 'patch'
        new_index.update(patch_index)

    with open(index_path, 'w') as f:
        json.dump(new_index, f, indent=2, sort_keys=True)


if __name__ == '__main__':
    update_index('/Users/ischnell/repo')
