import json
import time
from os.path import join


def parse_rawspec(data):
    spec = {}
    exec data.replace('\r', '') in spec
    spec['name'] = spec['name'].lower().replace('-', '_')
    res = {}
    for k in ('name', 'version', 'build',
              'arch', 'platform', 'osdist', 'python', 'packages'):
        res[k] = spec[k]
    return res


def info_from_z(z):
    res = dict(type='egg')
    arcname = 'EGG-INFO/spec/depend'
    if arcname not in z.namelist():
        raise KeyError("arcname=%r not in zip-file %s" % arcname)
    res.update(parse_rawspec(z.read(arcname)))

    arcname = 'EGG-INFO/spec/app.json'
    if arcname in z.namelist():
        res['app'] = True
        res.update(json.loads(z.read(arcname)))
    return res


def create_info(egg, extra_info=None):
    info = dict(key=egg.fn)
    info.update(info_from_z(egg.z))
    info['ctime'] = time.ctime()
    info['hook'] = egg.hook
    if extra_info:
        info.update(extra_info)
    with open(join(egg.meta_dir, 'info.json'), 'w') as fo:
        json.dump(info, fo, indent=2, sort_keys=True)
