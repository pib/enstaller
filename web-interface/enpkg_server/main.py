import sys
import time
import subprocess
from os.path import dirname, isfile, join

this_dir = dirname(__file__)
sys.path.insert(0, this_dir)

from bottle import get, post, request, run, view, debug, route, static_file

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


@get('/')
@view(join(this_dir, 'update'))
def update():
    print "Called update"
    lst = []
    for i, (package, version, repo) in enumerate(get_installed(sys.prefix)):
        lst.append(('#fff' if i % 2 else '#ccc',
                    package, version, repo, 'install'))
    return {'items': lst}


@post('/action')
def action():
    print 'request.forms', request.forms.dict
    return update()


@route('/static/:path#.+#')
def server_static(path):
    return static_file(path, root=this_dir)


def main():
    if '-b' in sys.argv:
        import webbrowser
        subprocess.call([sys.executable, webbrowser.__file__, '-t',
                         'http://localhost:8080/'])

    run(host='localhost', port=8080)


if __name__ == '__main__':
    main()
