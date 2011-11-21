# don't use this
from pprint import pprint
from os.path import join

from enstaller.indexed_repo.metadata import spec_from_dist, is_valid_eggname

from local_simple import LocalSimpleRepo


class LocalEggRepo(LocalSimpleRepo):

    def is_valid_key(self, key):
        return is_valid_eggname(key)

    def get_metadata(self, key, default=None):
        info = super(LocalEggRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(spec_from_dist(self.path(key)))
        return info


if __name__ == '__main__':
    r1 = LocalEggRepo('/Users/ischnell/repo')
    #fn = 'bsdiff4-1.0.2-1.egg'
    #print r1.get_metadata(fn)
    #for key in r1.query_keys(arch='amd64'):
    #    print key
    """
    for key, info in r1.query().iteritems():
        assert r1.get_metadata(key) == info
    r1._read_index()
    pprint(r1._index)
    """
    r1.update_index(1)
