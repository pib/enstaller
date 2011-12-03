import json
import re
from os.path import isfile, join


def read_depend(path):
    d = {}
    execfile(path, d)
    res = {}
    for k in ('name', 'version', 'build',
              'arch', 'platform', 'osdist', 'python', 'packages'):
        res[k] = d[k]
    return res


def create(egg):
    info = read_depend(join(egg.meta_dir, 'spec', 'depend'))
    info.update(json.load(open(join(egg.meta_dir, 'spec', 'app.json'))))

    reg_lines = []
    pat = re.compile(r'([\w.]+)\s+([\w.]+-\d+)$')
    for rs in ['%(name)s %(version)s-%(build)d' % info] + info['packages']:
        m = pat.match(rs)
        if not m:
            print "Warning: not a full requirement:", rs
            continue
        pkg = '%s-%s' % (m.group(1).lower(), m.group(2))
        reg_path = join(egg.pkgs_dir, pkg, 'EGG-INFO', 'registry.txt')
        if not isfile(reg_path):
            print "Warning: no registry file:", reg_path
            continue
        for line in open(reg_path):
            reg_lines.append(line.strip())
    info['reg_lines'] = reg_lines

    path = join(egg.meta_dir, 'app.json')
    with open(path, 'w') as f:
        json.dump(info, f, indent=2, sort_keys=True)
