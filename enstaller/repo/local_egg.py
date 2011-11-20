from pprint import pprint
from os.path import join

from enstaller.indexed_repo.metadata import (spec_from_dist, update_index,
                                             parse_depend_index)

from local_simple import LocalSimpleRepo


class LocalEggRepo(LocalSimpleRepo):

    def _update_fs_index(self):
        update_index(self.root_dir)

    def set(self, key, value, buffer_size=1048576):
        super(LocalEggRepo, self).set(key, value, buffer_size)
        self._update_fs_index()

    def delete(self, key):
        super(LocalEggRepo, self).delete(key)
        self._update_fs_index()

    def _read_index(self):
        self._index = parse_depend_index(open(join(
                    self.root_dir, 'index-depend.txt')).read())

    def get_metadata(self, key, default=None):
        info = super(LocalEggRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(spec_from_dist(self.path(key)))
        return info


if __name__ == '__main__':
    r1 = LocalEggRepo('/Users/ischnell/repo')
    r1._update_fs_index()
    #fn = 'bsdiff4-1.0.2-1.egg'
    #print r1.get_metadata(fn)
    #for key in r1.query_keys(type='egg', arch='amd64'):
    #    print key
    for key, info in r1.query().iteritems():
        assert r1.get_metadata(key) == info
    r1._read_index()
    pprint(r1._index)
