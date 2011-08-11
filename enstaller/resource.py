import sys
import json
from collections import defaultdict
from os.path import expanduser, join

from plat import custom_plat
from utils import get_installed_info
from indexed_repo.chain import Chain, Req
from indexed_repo.dist_naming import split_dist, split_eggname
from indexed_repo.requirement import add_Reqs_to_spec



class Resources(object):

    def __init__(self, urls, verbose=False):
        self.verbose = verbose
        self.index = []
        self.chain = Chain(verbose=verbose)
        for url in urls:
            self.add_product(url)


    def add_product(self, url):
        if not url.endswith('/'):
            url += '/'
        if self.verbose:
            print "Adding product:"
            print "   URL:", url

        if url.startswith('file://'):
            path = url[7:]
            fi = open(join(path, 'index-%s.json' % custom_plat))
            index = json.load(fi)
            fi.close()
        else:
            raise Exception

        if 'eggs' in index:
            self._add_egg_repos(url, index)

        self.index.append(index)


    def _add_egg_repos(self, url, index):
        if 'egg_repos' in index:
            repos = [url + path + '/' for path in index['egg_repos']]
        else:
            repos = [url]
        self.chain.repos.extend(repos)

        for cname, project in index['eggs'].iteritems():
            for distname, data in project['files'].iteritems():
                name, version, build = split_eggname(distname)
                spec = dict(metadata_version='1.1',
                            name=name, version=version, build=build,
                            python=data.get('python', '2.7'),
                            packages=data.get('depends', []))
                add_Reqs_to_spec(spec)
                assert spec['cname'] == cname, distname
                dist = repos[data.get('repo', 0)] + distname
                self.chain.index[dist] = spec
                self.chain.groups[cname].append(dist)


    def get_status(self):
        import egginst
        # the result is a dict mapping cname to ...
        res = {}
        for cname in egginst.get_installed_cnames(sys.prefix):
            d = defaultdict(str)
            info = get_installed_info(sys.prefix, cname)
            if info is None:
                continue
            d.update(info)
            res[cname] = d

            c = self.chain
            for cname in c.groups.iterkeys():
                dist = c.get_dist(Req(cname))
                if dist is None:
                    continue
                repo, fn = split_dist(dist)
                n, v, b = split_eggname(fn)
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
    r = Resources(['file://' + expanduser('~/buildware/scripts')])

    req = Req('epd')
    print r.chain.get_dist(req)
    r.chain.print_repos()
    for v in r.get_status().itervalues():
        print '%(name)-20s %(version)16s %(a-ver)16s %(status)12s' % v
