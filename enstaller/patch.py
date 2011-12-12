import os
import re
import json
import string
from os.path import abspath, getsize, getmtime, isdir, isfile, join

from utils import comparable_version, info_file
from egg_meta import is_valid_eggname, split_eggname
try:
    import zdiff
except ImportError:
    zdiff = None


fn_pat = re.compile(r'([\w.]+)-([\w.]+)-(\d+)--([\w.]+)-(\d+)\.zdiff$')
def split(fn):
    m = fn_pat.match(fn)
    if m is None:
        raise Exception("Can not split: %r" % fn)
    return m.expand(r'\1-\2-\3.egg'), m.expand(r'\1-\4-\5.egg')


def update_patches(eggs_dir, patches_dir, verbose=False):

    def calculate_all_patches():
        egg_names = [fn for fn in os.listdir(eggs_dir)
                     if is_valid_eggname(fn)]
        names = set(split_eggname(egg_name)[0]
                    for egg_name in egg_names)
        for name in sorted(names, key=string.lower):
            versions = []
            for egg_name in egg_names:
                n, v, b = split_eggname(egg_name)
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
        if verbose:
            print 'creating', patch_fn
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


def update_index(eggs_dir, patches_dir, force=False):
    index_path = join(patches_dir, 'index.json')
    if force or not isfile(index_path):
        index = {}
    else:
        index = json.load(open(index_path))

    new_index = {}
    for patch_fn in os.listdir(patches_dir):
        if not fn_pat.match(patch_fn):
            continue
        src_fn, dst_fn = split(patch_fn)
        dst_path = join(eggs_dir, dst_fn)
        dst_size = getsize(dst_path)
        if dst_size < 131072:
            continue
        patch_path = join(patches_dir, patch_fn)
        if dst_size < getsize(patch_path) * 2:
            continue
        info = index.get(patch_fn)
        if info and getmtime(patch_path) == info['mtime']:
            new_index[patch_fn] = info
            continue
        info = info_file(patch_path)
        info.update(zdiff.info(patch_path))
        info['name'] = patch_fn.split('-')[0].lower()
        new_index[patch_fn] = info

    with open(index_path, 'w') as f:
        json.dump(new_index, f, indent=2, sort_keys=True)


def update(eggs_dir, force=False, verbose=False):
    if zdiff is None:
        print "Warning: could not import bsdiff4, cannot create patches"
        return

    patches_dir = join(eggs_dir, 'patches')
    if not isdir(patches_dir):
        os.mkdir(patches_dir)

    if force:
        index_files = ['index.json']
        for fn in os.listdir(patches_dir):
            if fn.endswith('.zdiff') or fn in index_files:
                os.unlink(join(patches_dir, fn))

    update_patches(eggs_dir, patches_dir, verbose)
    update_index(eggs_dir, patches_dir)


def main():
    from optparse import OptionParser

    p = OptionParser(
        usage="usage: %prog [options] [DIRECTORY]",
        description="updates egg patches, for a given egg repository.  "
                    "DIRECTORY defaults to CWD")

    p.add_option('-f', "--force", action="store_true")
    p.add_option('-v', "--verbose", action="store_true")

    opts, args = p.parse_args()

    if len(args) == 0:
        dir_path = os.getcwd()
    elif len(args) == 1:
        dir_path = abspath(args[0])
    else:
        p.error("too many arguments")

    update(dir_path, opts.force, opts.verbose)


if __name__ == '__main__':
    main()
