from os.path import join

from enstaller.indexed_repo.metadata import (spec_from_dist, update_index,
                                             parse_depend_index)

from local_simple import LocalSimpleRepo


class LocalEggRepo(LocalSimpleRepo):

    def set(self, key, value, buffer_size=1048576):
        super(LocalEggRepo, self).set(key, value, buffer_size)
        update_index(self.root_dir)

    def delete(self, key):
        super(LocalEggRepo, self).delete(key)
        update_index(self.root_dir)

    def _read_index(self):
        self._index = parse_depend_index(open(join(
                    self.root_dir, 'index-depend.txt')).read())

    def get_metadata(self, key, default=None):
        info = super(LocalEggRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(spec_from_dist(self.path(key)))
        return info

    def query(self, **kwargs):
        res = {}
        for key in self.query_keys(**kwargs):
            res[key] = self._index[key]
        return res

    def query_keys(self, **kwargs):
        self._read_index()
        for key, info in self._index.iteritems():
            if all(info.get(k) in (v, None)
                   for k, v in kwargs.iteritems()):
                yield key


if __name__ == '__main__':
    from pprint import pprint
    r1 = LocalEggRepo('/Users/ischnell/repo')
    #fn = 'bsdiff4-1.0.2-1.egg'
    #print r1.get_metadata(fn)
    #for key in r1.query_keys(arch='amd64'):
    #    print key
    #pprint(r1.query(platform='win32'))
    for key, info in r1.query().iteritems():
        print key
        assert r1.get_metadata(key) == info
