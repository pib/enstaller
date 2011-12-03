import json
import re
from os.path import isfile, join
from registry import REGISTRY_CODE


def read_depend(path):
    d = {}
    execfile(path, d)
    res = {}
    for k in ('name', 'version', 'build',
              'arch', 'platform', 'osdist', 'python', 'packages'):
        res[k] = d[k]
    return res


def registry_lines(pkgs_dir, info):
    pat = re.compile(r'([\w.]+)\s+([\w.]+-\d+)$')
    for rs in ['%(name)s %(version)s-%(build)d' % info] + info['packages']:
        m = pat.match(rs)
        if not m:
            print "Warning: not a full requirement:", rs
            continue
        pkg = '%s-%s' % (m.group(1).lower(), m.group(2))
        reg_path = join(pkgs_dir, pkg, 'EGG-INFO', 'registry.txt')
        if not isfile(reg_path):
            print "Warning: no registry file:", reg_path
            continue
        for line in open(reg_path):
            yield line.strip()


def create_entry(path):
    """
    create entry point Python script at 'path', which sets up registry
    for the packages ... according to app.json
    """
    fo = open(path, 'w')
    fo.write(REGISTRY_CODE)
    fo.write("""
def run_app():
    import json
    from os.path import dirname, join

    info = json.load(open(join(dirname(__file__), 'app.json')))
    update_registry(info['reg_lines'])
    entry = info['entry']
    assert entry.count(':') == 1
    module, func = entry.strip().split(':')
    exec("from %(module)s import %(func)s\\n"
         "sys.exit(%(func)s())\\n" % locals())

if __name__ == '__main__':
    run_app()
""")
    fo.close()


def create(egg):
    info = read_depend(join(egg.meta_dir, 'spec', 'depend'))
    info.update(json.load(open(join(egg.meta_dir, 'spec', 'app.json'))))

    if egg.hook:
        info['reg_lines'] = list(registry_lines(egg.pkgs_dir, info))
    else:
        info['reg_lines'] = []

    path = join(egg.meta_dir, 'app.json')
    with open(path, 'w') as f:
        json.dump(info, f, indent=2, sort_keys=True)

    create_entry(join(egg.meta_dir, 'run_app.py'))
