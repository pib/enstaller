"""\
web-interface for enpkg command
"""
import sys
import time
import subprocess
import socket
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
    for i, (pkg, version, repo) in enumerate(get_installed(sys.prefix)):
        lst.append(('i%d' % (i % 2), pkg, version, repo, i % 3 == 2))
    return {'items': lst}


@post('/action')
def action():
    print 'request.forms', request.forms.dict
    return update()


@route('/static/:path#.+#')
def server_static(path):
    return static_file(path, root=this_dir)


def create_static_html():
    import tempfile

    tmp_dir = tempfile.mkdtemp()
    index_html = join(tmp_dir, 'index.html')

    fo = open(index_html, 'w')
    fo.write("I'm a static file\n")
    fo.close()

    return index_html


def main():
    from optparse import OptionParser

    p = OptionParser(usage="usage: %prog [options]", description=__doc__)

    p.add_option('-b', "--browser",
                 action="store_true",
                 help="lauch a web-browser")

    p.add_option('-p', "--port",
                 action="store",
                 default=8080,
                 help="defaults to %default")

    opts, args = p.parse_args()

    port = int(opts.port)
    url = 'http://localhost:%d/' % port

    if '-b' in sys.argv:
        import webbrowser
        print 'opening in web-browser:', url
        webbrowser.open_new_tab(url)

#    try:
    run(host='localhost', port=port)
#    except socket.error:
#        print "Could not start web server, creating static html file"
#        url = 'file://%s' % create_static_html()


if __name__ == '__main__':
    main()
