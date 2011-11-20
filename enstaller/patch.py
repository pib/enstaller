import os
import re
import json
import string
from glob import glob
from cStringIO import StringIO
from collections import defaultdict
from urllib2 import HTTPError
from os.path import basename, getsize, getmtime, isdir, isfile, join

#from enstaller.repo.local_patch import LocalPatchRepo, fn_pat
from enstaller.repo.local_simple import LocalSimpleRepo

from egginst.utils import pprint_fn_action, console_progress
from utils import stream_to_file, comparable_version, info_file
from enstaller.indexed_repo import dist_naming
import zdiff


fn_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)--([\w.]+)-(\d+)\.zdiff$')
def split(fn):
    m = fn_pat.match(fn)
    if m is None:
        raise Exception("Can not split: %r" % fn)
    return m.expand(r'\1-\2-\3.egg'), m.expand(r'\1-\4-\5.egg')


def update_patches(eggs_dir, patches_dir):

    def calculate_all_patches():
        egg_names = [fn for fn in os.listdir(eggs_dir)
                     if dist_naming.is_valid_eggname(fn)]
        names = set(dist_naming.split_eggname(egg_name)[0]
                    for egg_name in egg_names)
        for name in sorted(names, key=string.lower):
            versions = []
            for egg_name in egg_names:
                n, v, b = dist_naming.split_eggname(egg_name)
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

    def up_to_date(patch_fn):
        patch_path = join(patches_dir, patch_fn)
        if not isfile(patch_path):
            return False
        info = zdiff.info(patch_path)
        for t in 'dst', 'src':
            if getmtime(join(eggs_dir, info[t])) != info[t + '_mtime']:
                return False
        return True

    def create(patch_fn):
        src_fn, dst_fn = split(patch_fn)
        src_path = join(eggs_dir, src_fn)
        dst_path = join(eggs_dir, dst_fn)
        assert isfile(src_path) and isfile(dst_path)
        print patch_fn
        patch_path = join(patches_dir, patch_fn)
        zdiff.diff(src_path, dst_path, patch_path + '.part')
        os.rename(patch_path + '.part', patch_path)

    all_patches = set()
    for patch_fn in calculate_all_patches():
        all_patches.add(patch_fn)
        if not up_to_date(patch_fn):
            create(patch_fn)

    # remove old patches
    for patch_fn in os.listdir(patches_dir):
        if patch_fn.endswith('.zdiff') and patch_fn not in all_patches:
            os.unlink(join(patches_dir, patch_fn))


def update_index(eggs_dir, patches_dir):
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
        info = info_file(patch_path)
        info.update(zdiff.info(patch_path))
        d[basename(patch_path)] = info
    with open(join(patches_dir, 'index.json'), 'w') as f:
        json.dump(d, f, indent=2, sort_keys=True)


def update(eggs_dir):
    patches_dir = join(eggs_dir, 'patches')
    if not isdir(patches_dir):
        os.mkdir(patches_dir)
    update_patches(eggs_dir, patches_dir)
    update_index(eggs_dir, patches_dir)


def patch(dist, fetch_dir):
    try:
        import zdiff
    except ImportError:
        print "Warning: cannot import zdiff"
        return False

    repo, fn = dist_naming.split_dist(dist)
    r = LocalSimpleRepo(join(repo[7:], 'patches'))
    #print r.query(dst=fn)

    possible = []
    for patch_fn, info in r.query(dst=fn).iteritems():
        src_fn, dst_fn = split(patch_fn)
        assert info['dst'] == dst_fn == fn
        assert info['src'] == src_fn
        src_path = join(fetch_dir, src_fn)
        #print '%8d %s %s %s' % (info['size'], patch_fn, src_fn, isfile(src_path))
        if isfile(src_path):
            possible.append((info['size'], patch_fn, src_fn, info['md5']))

    if not possible:
        return False

    size, patch_fn, src_fn, md5 = min(possible)

    pprint_fn_action(patch_fn, 'downloading')
    patch_path = join(fetch_dir, patch_fn)
    stream_to_file(patch_path, r.get(patch_fn), md5, size,
                   console_progress)

    pprint_fn_action(patch_fn, 'patching')
    zdiff.patch(src_path, join(fetch_dir, fn), patch_path,
                progress_callback=console_progress)

    return True


if __name__ == '__main__':
    update('/Users/ischnell/repo')
