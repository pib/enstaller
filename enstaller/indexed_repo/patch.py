import re
from cStringIO import StringIO
from collections import defaultdict
from urllib2 import HTTPError
from os.path import isfile, join

from egginst.utils import pprint_fn_action, console_file_progress
from enstaller.utils import write_data_from_url
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

    try:
        faux = StringIO()
        write_data_from_url(faux, repo + 'patches/index.txt')
        index_data = faux.getvalue()
        faux.close()
    except HTTPError:
        index[repo] = False
        return

    index[repo] = defaultdict(list)
    for line in index_data.splitlines():
        md5, size, patch_fn = line.split()
        size = int(size)
        src_fn, dst_fn = split(patch_fn)
        index[repo][dst_fn].append((size, patch_fn, md5))


def patch(dist, fetch_dir):
    repo, fn = dist_naming.split_dist(dist)
    read_index(repo)
    if index[repo] is False:
        print "Warning: no patches for %r exist" % repo
        return False

    for size, patch_fn, md5 in sorted(index[repo][fn]):
        src_fn, dst_fn = split(patch_fn)
        assert dst_fn == fn
        src_path = join(fetch_dir, src_fn)
        print '%8d %s %s %s' % (size, patch_fn, src_fn, isfile(src_path))
        if isfile(src_path):
            break
    else:
        return False

    pprint_fn_action(patch_fn, 'downloading')
    patch_path = join(fetch_dir, patch_fn)
    fo = open(patch_path, 'wb')
    write_data_from_url(fo, repo + 'patches/' + patch_fn, md5=md5, size=size,
                        progress_callback=console_file_progress)
    fo.close()

    zdiff.patch(src_path, join(fetch_dir, fn), patch_path)

    return True
