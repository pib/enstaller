import os
from os.path import abspath, join

from enstaller.indexed_repo.dist_naming import is_valid_eggname
from enstaller.indexed_repo.metadata import spec_from_dist

from local_simple import LocalSimpleRepo


class LocalEggRepo(LocalSimpleRepo):

    def get_metadata(self, key, default=None):
        info = super(LocalEggRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(spec_from_dist(self.path(key)))
        return info

    def query_keys(self, **kwargs):
        if kwargs:
            return
        for fn in os.listdir(self.root_dir):
            if not is_valid_eggname(fn):
                continue
            yield abspath(join(self.root_dir, fn))[self._len_abspath + 1:]


if __name__ == '__main__':
    r1 = LocalEggRepo('/Users/ischnell/repo')
    fn = 'bsdiff4-1.0.2-1.egg'
    print r1.get_metadata(fn)
    print r1.query()
