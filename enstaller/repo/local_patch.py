from pprint import pprint
from os.path import join

from enstaller.patch import update_patches
import enstaller.zdiff as zdiff

from local_simple import LocalSimpleRepo


class LocalPatchRepo(LocalSimpleRepo):

    def _update_fs_index(self):
        update_patches(join(self.root_dir, '..'))

    def set(self, key, value, buffer_size=1048576):
        raise

    def delete(self, key):
        raise

    def get_metadata(self, key, default=None):
        info = super(LocalPatchRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(zdiff.info(self.path(key)))
        return info


if __name__ == '__main__':
    r1 = LocalPatchRepo('/Users/ischnell/repo/patches')
    r1._update_fs_index()
    for key, info in r1.query().iteritems():
        assert r1.get_metadata(key) == info
    r1._read_index()
    pprint(r1._index)
