import sys
import os.path
import csv

from bottle import get, put, run, view, debug, route, static_file

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
            path = os.path.join(info['meta_dir'], '__enpkg__.txt')
            if os.path.isfile(path):
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
