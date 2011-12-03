import re
import os
import json
import zipfile
from os.path import getmtime, isfile, join

from utils import info_file


egg_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)\.egg$')

def is_valid_eggname(eggname):
    return bool(egg_pat.match(eggname))

def split_eggname(eggname):
    m = egg_pat.match(eggname)
    assert m, eggname
    return m.group(1), m.group(2), int(m.group(3))


def parse_rawspec(data):
    spec = {}
    exec data.replace('\r', '') in spec
    spec['name'] = spec['name'].lower()
    res = {}
    for k in ('name', 'version', 'build',
              'arch', 'platform', 'osdist', 'python', 'packages'):
        res[k] = spec[k]
    return res

def info_from_egg(path):
    res = dict(type='egg')
    z = zipfile.ZipFile(path)
    arcname = 'EGG-INFO/spec/depend'
    if arcname not in z.namelist():
        z.close()
        raise KeyError("arcname=%r not in zip-file %s" % (arcname, path))
    res.update(parse_rawspec(z.read(arcname)))

    arcname = 'EGG-INFO/spec/app.json'
    if arcname in z.namelist():
        res['app'] = True
        res.update(json.loads(z.read(arcname)).iteritems())
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
