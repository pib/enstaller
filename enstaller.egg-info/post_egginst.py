"""
converts the old "__egginst__.txt" files to "egginst.json"
and "_info.json" files
"""
import os
import re
import sys
import json
import time
from os.path import abspath, isdir, isfile, join


def read_old(path):
    d1 = {'installed_size': -1}
    execfile(path, d1)
    d2 = {}
    for name in ['egg_name', 'prefix', 'installed_size', 'rel_files']:
        d2[name] = d1[name]
    return d2


def write_egginst(path, d):
    d['files'] = []
    for f in d['rel_files'] + [path]:
        p = abspath(join(sys.prefix, f))
        d['files'].append(p.replace(sys.prefix, '.').replace('\\', '/')
                          if p.startswith(sys.prefix) else p)
    del d['rel_files']
    d['prefix'] = sys.prefix

    with open(path, 'w') as f:
        json.dump(d, f, indent=2, sort_keys=True)


egg_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)\.egg$')
def write_info(path, eggname):
    m = egg_pat.match(eggname)
    if m is None:
        return
    n, v, b = m.group(1), m.group(2), int(m.group(3))
    info = dict(
        key = eggname,
        name = n.lower(),
        version = v,
        build = b,
        ctime = time.ctime(),
        hook = False,
    )
    with open(path, 'w') as f:
        json.dump(info, f, indent=2, sort_keys=True)



def get_eggname():
    from enstaller import __version__
    return 'enstaller-%s-1.egg' % __version__


def main():
    egg_info_dir = join(sys.prefix, 'EGG-INFO')
    for fn in os.listdir(egg_info_dir):
        meta_dir = join(egg_info_dir, fn)
        if not isdir(meta_dir):
            continue
        path1 = join(meta_dir, '__egginst__.txt')
        if not isfile(path1):
            continue
        path2 = join(meta_dir, 'egginst.json')
        path3 = join(meta_dir, '_info.json')
        if isfile(path2) and isfile(path3):
            continue
        data = read_old(path1)
        write_egginst(path2, data)
        write_info(path3, data['egg_name'])

    # create files for enstaller itself if necessary
    meta_dir = join(egg_info_dir, 'enstaller')
    path2 = join(meta_dir, 'egginst.json')
    if not isfile(path2):
        write_egginst(path2, dict(
                egg_name=get_eggname(), prefix=sys.prefix,
                installed_size=-1, rel_files=[]))
    path3 = join(meta_dir, '_info.json')
    if not isfile(path3):
        write_info(path3, get_eggname())


if __name__ == '__main__':
    main()
