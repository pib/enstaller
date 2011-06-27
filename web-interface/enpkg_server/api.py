import sys
from collections import defaultdict

import egginst

from enstaller.indexed_repo import Chain, Req, dist_naming
from enstaller.utils import get_installed_info, comparable_version
import enstaller.config as config


def get_status():
    # the result is a dict mapping cname to ...
    res = {}
    for cname in egginst.get_installed_cnames(sys.prefix):
        d = defaultdict(str)
        info = get_installed_info(sys.prefix, cname)
        if info is None:
            continue
        d.update(info)
        res[cname] = d

    c = Chain(config.get('IndexedRepos'))

    for cname in c.groups.iterkeys():
        dist = c.get_dist(Req(cname))
        if dist is None:
            continue
        repo, fn = dist_naming.split_dist(dist)
        n, v, b = dist_naming.split_eggname(fn)
        if cname not in res:
            d = defaultdict(str)
            d['name'] = n
            res[cname] = d
        res[cname]['a-egg'] = fn
        res[cname]['a-ver'] = '%s-%d' % (v, b)

    def vb_egg(fn):
        try:
            n, v, b = dist_naming.split_eggname(fn)
            return comparable_version(v), b
        except:
            return None

    for d in res.itervalues():
        if d['egg_name']:                    # installed
            if d['a-egg']:
                if vb_egg(d['egg_name']) >= vb_egg(d['a-egg']):
                    d['status'] = 'up-to-date'
                else:
                    d['status'] = 'updateable'
            else:
                d['status'] = 'installed'
        else:                                # not installed
            if d['a-egg']:
                d['status'] = 'installable'
    return res


if __name__ == '__main__':
    for v in get_status().itervalues():
        print '%(name)-20s %(version)16s %(a-ver)16s %(status)12s' % v
