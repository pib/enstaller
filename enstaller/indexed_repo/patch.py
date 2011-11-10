import re
from cStringIO import StringIO
from collections import defaultdict
from os.path import isfile, join

from enstaller.utils import md5_file, write_data_from_url
import enstaller.zdiff as zdiff

import dist_naming


fn_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)--([\w.]+)-(\d+)\.zdiff$')
def split(fn):
    m = fn_pat.match(fn)
    if m is None:
        raise Exception("Can not split: %r" % fn)
    return m.expand(r'\1-\2-\3.egg'), m.expand(r'\1-\4-\5.egg')


def patch(dist, fetch_dir):
    repo, fn = dist_naming.split_dist(dist)
    patches_url = repo + 'patches/'

    faux = StringIO()
    write_data_from_url(faux, patches_url + 'index.txt')
    index_data = faux.getvalue()
    faux.close()

    patches = defaultdict(list)
    for line in index_data.splitlines():
        md5, size, patch_fn = line.split()
        src_fn, dst_fn = split(patch_fn)
        patches[dst_fn].append((size, patch_fn, src_fn, md5))

    # -----------

    for size, patch_fn, src_fn, md5 in sorted(patches[fn]):
        path = join(fetch_dir, src_fn)
        print size, patch_fn, src_fn, isfile(path)
        if isfile(path):
            break
    else:
        return False

    patch_path = join(fetch_dir, patch_fn)
    fo = open(patch_path, 'wb')
    write_data_from_url(fo, patches_url + patch_fn, size=size)
    fo.close()
    assert md5_file(patch_path) == md5

    zdiff.patch(join(fetch_dir, src_fn),
                join(fetch_dir, fn),
                patch_path)

    return True
