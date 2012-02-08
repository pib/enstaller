"""
A .zdiff is a diff of two zip-files.
It is an (uncompressed) zip-file where each archive contains information
about how SRC needs to be modified to obtain DST.  A non-existing archive
means the SRC is unchanged.  The data in the archives always has to start
with one of the following:
  * BSDIFF4: the following data is a binary diff between SRC and DST
  * BZ: the new data of DST (bz2 compressed), SRC is ignored
  * RM: DST does not exist (it needs removed from SRC)

"""
import bz2
import json
import zipfile
from uuid import uuid4
from os.path import basename, getmtime, getsize

from utils import md5_file

import bsdiff4


def diff(src_path, dst_path, patch_path):
    x = zipfile.ZipFile(src_path)
    y = zipfile.ZipFile(dst_path)
    z = zipfile.ZipFile(patch_path, 'w', zipfile.ZIP_STORED)

    xnames = set(x.namelist())
    ynames = set(y.namelist())

    count = 0
    for name in xnames | ynames:
        xdata = x.read(name) if name in xnames else None
        ydata = y.read(name) if name in ynames else None
        if xdata == ydata:
            continue

        if ydata is not None:
            bz2_data = bz2.compress(ydata) # startswith BZ

        if xdata is not None and ydata is not None:
            diff_data = bsdiff4.diff(xdata, ydata)
            if len(diff_data) < len(bz2_data):
                zdata = diff_data # startswith BSDIFF4
            else:
                zdata = bz2_data
        elif xdata is not None and ydata is None:
            zdata = 'RM'
        elif ydata is not None and xdata is None:
            zdata = bz2_data
        else:
            raise Exception("Hmm, didn't expect to get here.")

        #print zdata[:2], name
        z.writestr(name, zdata)
        count += 1

    info = {}
    for path, pre in (src_path, 'src'), (dst_path, 'dst'):
        info.update({pre: basename(path),
                     pre + '_size': getsize(path),
                     pre + '_mtime': getmtime(path),
                     pre + '_md5': md5_file(path)})
    z.writestr('__zdiff_info__.json',
               json.dumps(info, indent=2, sort_keys=True))
    z.close()
    y.close()
    x.close()
    return count


def patch(src_path, dst_path, patch_path, evt_mgr=None, super_id=None):
    if evt_mgr:
        from encore.events.api import ProgressManager
    else:
        from egginst.console import ProgressManager

    x = zipfile.ZipFile(src_path)
    y = zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED)
    z = zipfile.ZipFile(patch_path)

    xnames = x.namelist()
    znames = set(z.namelist())

    n = 0
    tot = len(xnames) + len(znames)

    progress = ProgressManager(
                evt_mgr, source=patch,
                operation_id=uuid4(),
                message="patching",
                steps=tot,
                # ---
                progress_type="patching", filename=basename(patch_path),
                disp_amount=str(tot),
                super_id=super_id)

    with progress:
        for name in xnames:
            if name not in znames:
                 y.writestr(x.getinfo(name), x.read(name))
            n += 1
            progress(step=n)

        for name in z.namelist():
            if name == '__zdiff_info__.json':
                continue
            zdata = z.read(name)
            if zdata.startswith('BSDIFF4'):
                ydata = bsdiff4.patch(x.read(name), zdata)
            elif zdata.startswith('BZ'):
                ydata = bz2.decompress(zdata)
            elif zdata.startswith('RM'):
                continue
            else:
                raise Exception("Hmm, didn't expect to get here: %r" % zdata)

            y.writestr(name, ydata)
            progress(step=n)

    z.close()
    y.close()
    x.close()


def info(patch_path):
    z = zipfile.ZipFile(patch_path)
    data = z.read('__zdiff_info__.json')
    z.close()
    return json.loads(data)


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3:
        src, dst = sys.argv[1:3]
    else:
        src, dst = 'nose-1.0.0-1.egg', 'nose-1.1.2-1.egg'

    pat = 'test.zdiff'
    diff(src, dst, pat)
    patch(src, dst + '2', pat)
    print info(pat)
    assert diff(dst, dst + '2', 'dummy.zdiff') == 0
