import os
import json
from os.path import getmtime, isfile, join

from enstaller.indexed_repo.dist_naming import is_valid_eggname
from enstaller.indexed_repo.metadata import spec_from_dist
from utils import info_file


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
        info.update(spec_from_dist(path))
        info['name'] = info['name'].lower()
        new_index[fn] = info

    with open(index_path, 'w') as f:
        json.dump(new_index, f, indent=2, sort_keys=True)


if __name__ == '__main__':
    update_index('/Users/ischnell/repo')
