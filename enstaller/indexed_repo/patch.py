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


index = {}
def read_index(repo):
    if repo in index:
        return

    faux = StringIO()
    write_data_from_url(faux, repo + 'patches/index.txt')
    index_data = faux.getvalue()
    faux.close()

    index[repo] = defaultdict(list)
    for line in index_data.splitlines():
        md5, size, patch_fn = line.split()
        src_fn, dst_fn = split(patch_fn)
        index[repo][dst_fn].append((size, patch_fn, md5))


def patch(dist, fetch_dir):
    repo, fn = dist_naming.split_dist(dist)
    read_index(repo)

    for size, patch_fn, md5 in sorted(index[repo][fn]):
        src_fn, dst_fn = split(patch_fn)
        assert dst_fn == fn
        src_path = join(fetch_dir, src_fn)
        #print size, patch_fn, src_fn, isfile(src_path)
        if isfile(src_path):
            break
    else:
        return False

    patch_path = join(fetch_dir, patch_fn)
    fo = open(patch_path, 'wb')
    write_data_from_url(fo, repo + 'patches/' + patch_fn, md5=md5, size=size)
    fo.close()

    zdiff.patch(src_path,
                join(fetch_dir, fn),
                patch_path)

    return True
