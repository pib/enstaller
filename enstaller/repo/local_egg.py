import json
from pprint import pprint
from os.path import join

from enstaller.indexed_repo.metadata import (spec_from_dist, update_index,
                                             parse_depend_index)
from enstaller.patch import update_patches
import enstaller.zdiff as zdiff

from local_simple import LocalSimpleRepo


class LocalEggRepo(LocalSimpleRepo):

    def _update_fs_index(self):
        update_index(self.root_dir)
        update_patches(self.root_dir)

    def set(self, key, value, buffer_size=1048576):
        super(LocalEggRepo, self).set(key, value, buffer_size)
        self._update_fs_index()

    def delete(self, key):
        super(LocalEggRepo, self).delete(key)
        self._update_fs_index()

    def _read_index(self):
        self._index = parse_depend_index(open(join(
                    self.root_dir, 'index-depend.txt')).read())
        for info in self._index.itervalues():
            info['type'] = 'egg'
        index_key = 'patches/index.json'
        if self.exists(index_key):
            for key, info in json.load(self.get(index_key)).iteritems():
                info['type'] = 'patch'
                self._index['patches/' + key] = info

    def get_metadata(self, key, default=None):
        info = super(LocalEggRepo, self).get_metadata(key, default)
        if info is default:
            return default
        if key.endswith('.egg'):
            info.update(spec_from_dist(self.path(key)))
            info['type'] = 'egg'
        elif key.endswith('.zdiff'):
            info.update(zdiff.info(self.path(key)))
            info['type'] = 'patch'
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
    r1 = LocalEggRepo('/Users/ischnell/repo')
    r1._update_fs_index()
    #fn = 'bsdiff4-1.0.2-1.egg'
    #print r1.get_metadata(fn)
    #for key in r1.query_keys(type='egg', arch='amd64'):
    #    print key
    #pprint(r1.query(type='patch'))
    for key, info in r1.query().iteritems():
        print key
        a, b = r1.get_metadata(key), info
        if a != b:
            pprint(a)
            pprint(b)
    #r1._read_index()
    #pprint(r1._index)
