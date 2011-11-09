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
import zipfile
import bz2

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

    z.close()
    y.close()
    x.close()
    return count


def patch(src_path, dst_path, patch_path):
    x = zipfile.ZipFile(src_path)
    y = zipfile.ZipFile(dst_path, 'w', zipfile.ZIP_DEFLATED)
    z = zipfile.ZipFile(patch_path)

    znames = set(z.namelist())
    for name in x.namelist():
        if name not in znames:
             y.writestr(x.getinfo(name), x.read(name))

    for name in z.namelist():
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

    z.close()
    y.close()
    x.close()


if __name__ == '__main__':
    import sys
    if len(sys.argv) == 3:
        src, dst = sys.argv[1:3]
    else:
        src, dst = 'nose-1.0.0-1.egg',  'nose-1.1.2-1.egg'

    diff(src, dst,  'test.zdiff')
    patch(src, dst + '2', 'test.zdiff')
    assert diff(dst, dst + '2', 'dummy.zdiff') == 0
