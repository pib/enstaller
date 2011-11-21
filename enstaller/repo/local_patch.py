# don't use this
import re
from pprint import pprint
from os.path import join

import enstaller.zdiff as zdiff

from local_simple import LocalSimpleRepo


fn_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)--([\w.]+)-(\d+)\.zdiff$')


class LocalPatchRepo(LocalSimpleRepo):

    def is_valid_key(self, key):
        return bool(fn_pat.match(key))

    def get_metadata(self, key, default=None):
        info = super(LocalPatchRepo, self).get_metadata(key, default)
        if info is default:
            return default
        info.update(zdiff.info(self.path(key)))
        return info


if __name__ == '__main__':
    r1 = LocalPatchRepo('/Users/ischnell/repo/patches')
    """
    r1.update_index()
    for key, info in r1.query().iteritems():
        assert r1.get_metadata(key) == info
    """
    #r1._read_index()
    #pprint(r1._index)
    print r1.query(dst='nose-1.1.2-1.egg')
