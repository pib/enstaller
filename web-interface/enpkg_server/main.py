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

from enstaller.main import get_status
import egginst


debug(True)


@get('/')
@view(join(this_dir, 'update'))
def update():
    print "Called update"
    lst = []
    status = get_status()
    for i, cname in enumerate(sorted(status.iterkeys())):
        d = status[cname]
        checkbok = d['status'].endswith('-able')
        cls = {'up-to-date': 'ok',
               'installed': 'ok',
               'update-able': 'up',
               'install-able': 'inst',
               }.get(d['status'], 'unknown')

        lst.append((cls,
                    d['name'], d['version'], d['a-ver'], d['status'],
                    checkbok))
    return {'items': lst}


@post('/action')
def action():
    print 'request.forms', request.forms.dict
    for name in request.forms.dict.iterkeys():
        subprocess.call(['enpkg', name])
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
