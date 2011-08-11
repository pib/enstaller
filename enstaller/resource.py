import json
from os.path import expanduser, join

from plat import custom_plat

from indexed_repo.chain import Chain, Req
from indexed_repo.dist_naming import split_eggname
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


if __name__ == '__main__':
    r = Resources(['file://' + expanduser('~/buildware/scripts')])

    req = Req('epd')
    print r.chain.get_dist(req)
    r.chain.print_repos()
