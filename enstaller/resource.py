import json
from os.path import dirname, expanduser

from indexed_repo.chain import Chain, Req



if __name__ == '__main__':
    path = expanduser('~/buildware/scripts/index.json')
    fi = open(path)
    index = json.load(fi)
    fi.close()
    index['url'] = 'file://%s/' % dirname(path)

    c = Chain([index], verbose=1)
    req = Req('epd 7.1-2')
    print c.get_dist(req)
    for dist in c.install_sequence(req):
        print dist_as_req(dist)
