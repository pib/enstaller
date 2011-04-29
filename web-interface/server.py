import sys
from os.path import isfile, join

from bottle import get, post, put, run, view, debug, route, static_file

from enstaller.main import get_installed_info, cname_fn, shorten_repo
import egginst


debug(True)

def get_installed(prefix, pat=None):
    results = []
    for fn in egginst.get_installed(prefix):
        if pat and not pat.search(fn[:-4]):
            continue
        lst = list(egginst.name_version_fn(fn))
        info = get_installed_info(prefix, cname_fn(fn))
        if info is None:
            lst.append('-')
        else:
            path = join(info['meta_dir'], '__enpkg__.txt')
            if isfile(path):
                d = {}
                execfile(path, d)
                lst.append(shorten_repo(d['repo']))
            else:
                lst.append('-')
        results.append(tuple(lst))
    return results



@get('/status')
@view('status2')
def main():
    return {'items': get_installed(sys.prefix)}


@get('/update')
@view('update')
def update():
    lst = []
    for i, (package, version, repo) in enumerate(get_installed(sys.prefix)):
        lst.append(('#fff' if i % 2 else '#ccc',
                    package, version, repo, 'install'))
    print lst
    return {'items': lst}


@post('/action/:pkg')
def action(pkg):
    assert pkg.startswith('pkg_')
    pkg = pkg[4:]
    print "ACTION:", pkg


@route('/static/:path#.+#')
def server_static(path):
    return static_file(path, root='.')


@get('/installed')
def installed():
    #return {
    #    'id': 'Package',
    #    'label': 'Package',
    #    'items': [dict(zip(['Package', 'Version', 'Repository'], pkg))
    #        for pkg in get_installed(sys.prefix)]
    #}
    return {'items': get_installed(sys.prefix)}


run(host='localhost', port=8080)
