import os
import re
import json
import string
from glob import glob
from cStringIO import StringIO
from collections import defaultdict
from urllib2 import HTTPError
from os.path import basename, getsize, getmtime, isdir, isfile, join

from egginst.utils import pprint_fn_action, console_file_progress
from utils import write_data_from_url, comparable_version, md5_file
from enstaller.indexed_repo import dist_naming
import zdiff


fn_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)--([\w.]+)-(\d+)\.zdiff$')
def split(fn):
    m = fn_pat.match(fn)
    if m is None:
        raise Exception("Can not split: %r" % fn)
    return m.expand(r'\1-\2-\3.egg'), m.expand(r'\1-\4-\5.egg')


def yield_all(url, py_ver):
    from enstaller.indexed_repo import Chain

    c = Chain(repos=[url])
    names = set()
    for dist in c.index.iterkeys():
        fn = dist_naming.filename_dist(dist)
        names.add(dist_naming.split_eggname(fn)[0])

    for name in sorted(names, key=string.lower):
        versions = []
        for dist, spec in c.index.iteritems():
            if spec['python'] and py_ver and spec['python'] != py_ver:
                continue
            fn = dist_naming.filename_dist(dist)
            n, v, b = dist_naming.split_eggname(fn)
            if n != name:
                continue
            versions.append((v, b))
        versions.sort(key=(lambda vb: (comparable_version(vb[0]), vb[1])))
        versions = ['%s-%d' % vb for vb in versions]
        lv = len(versions)
        #print name, lv, versions
        for i in xrange(0, lv):
            for j in xrange(i + 1, lv):
                yield '%s-%s--%s.zdiff' % (name, versions[i], versions[j])


def update_patches(eggs_dir, py_ver='2.7'):
    patches_dir = join(eggs_dir, 'patches')
    if not isdir(patches_dir):
        os.mkdir(patches_dir)

    for patch_fn in yield_all('file://' + eggs_dir, py_ver):
        patch_path = join(patches_dir, patch_fn)
        if isfile(patch_path):
            continue
        src_fn, dst_fn = split(patch_fn)
        src_path = join(eggs_dir, src_fn)
        dst_path = join(eggs_dir, dst_fn)
        assert isfile(src_path) and isfile(dst_path)
        #print src_fn, dst_fn, patch_fn
        zdiff.diff(src_path, dst_path, patch_path + '.part')
        os.rename(patch_path + '.part', patch_path)

    d = {}
    for patch_path in sorted(glob(join(patches_dir, '*.zdiff')),
                             key=string.lower):
        src_fn, dst_fn = split(basename(patch_path))
        dst_path = join(eggs_dir, dst_fn)
        dst_size = getsize(dst_path)
        if dst_size < 131072:
            continue
        patch_size = getsize(patch_path)
        if dst_size < patch_size * 2:
            continue
        info = dict(size=getsize(patch_path),
                    mtime=getmtime(patch_path),
                    md5=md5_file(patch_path))
        info.update(zdiff.info(patch_path))
        d[basename(patch_path)] = info
    json.dump(d, open(join(patches_dir, 'index.json'), 'w'), indent=2)


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
    try:
        import zdiff
    except ImportError:
        print "Warning: cannot import zdiff"
        return False

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

    pprint_fn_action(patch_fn, 'patching')
    zdiff.patch(src_path, join(fetch_dir, fn), patch_path,
                progress_callback=console_file_progress)

    return True
