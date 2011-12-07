import json
import time
from os.path import basename, join


def parse_rawspec(data):
    spec = {}
    exec data.replace('\r', '') in spec
    spec['name'] = spec['name'].lower()
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


def create_info(egg):
    info = dict(key=basename(egg.fpath))
    info.update(info_from_z(egg.z))
    info['install_time'] = time.ctime()
    info['meta_dir'] = egg.meta_dir
    info['prefix'] = egg.prefix
    with open(join(egg.meta_dir, 'info.json'), 'w') as fo:
        json.dump(info, fo, indent=2, sort_keys=True)
