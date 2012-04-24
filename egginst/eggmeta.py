import json
import time
from os.path import join


def parse_rawspec(data):
    spec = {}
    exec data.replace('\r', '') in spec
    res = {}
    for k in ('name', 'version', 'build',
              'arch', 'platform', 'osdist', 'python', 'packages'):
        res[k] = spec[k]
    return res


def info_from_z(z):
    res = dict(type='egg')

    arcname = 'EGG-INFO/spec/depend'
    if arcname in z.namelist():
        res.update(parse_rawspec(z.read(arcname)))

    arcname = 'EGG-INFO/info.json'
    if arcname in z.namelist():
        res.update(json.loads(z.read(arcname)))

    res['name'] = res['name'].lower().replace('-', '_')
    return res


def create_info(egg, extra_info=None):
    info = dict(key=egg.fn)
    info.update(info_from_z(egg.z))
    info['ctime'] = time.ctime()
    info['hook'] = egg.hook
    if extra_info:
        info.update(extra_info)

    try:
        del info['available']
    except KeyError:
        pass

    with open(join(egg.meta_dir, '_info.json'), 'w') as fo:
        json.dump(info, fo, indent=2, sort_keys=True)

    return info
