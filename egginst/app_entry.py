import re
from os.path import isfile, join
from registry import REGISTRY_CODE


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
            #print "Warning: no registry file:", reg_path
            continue
        for line in open(reg_path):
            line = line.strip()
            if line.startswith('#'):
                yield line
            else:
                k, v = line.split(None, 1)
                assert v.startswith('../'), v
                yield '%s  ../../%s/%s' % (k, pkg, v[3:])


def create_entry_script(path, entry):
    """
    create entry point Python script at 'path', which reads app_registry.txt
    """
    assert entry.count(':') == 1
    module, func = entry.strip().split(':')
    fo = open(path, 'w')
    fo.write(REGISTRY_CODE)
    fo.write("""
if __name__ == '__main__':
    from os.path import isfile
    path = join(dirname(__file__), 'app_registry.txt')
    if isfile(path):
        update_registry([path])
    else:
        print "Warning: no registry file:", path
    from %(module)s import %(func)s
    sys.exit(%(func)s())
""" % locals())
    fo.close()


def create_entry(egg, info):
    if egg.hook:
        with open(join(egg.meta_dir, 'app_registry.txt'), 'w') as fo:
            for line in registry_lines(egg.pkgs_dir, info):
                fo.write('%s\n' % line)

    app_entry = info.get('app_entry')
    if app_entry:
        create_entry_script(join(egg.meta_dir, 'app_entry.py'), app_entry)
