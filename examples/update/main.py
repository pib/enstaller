"""\
This program creates an egg package (called update_NAME-1.0.egg),
for uptaing the package NAME.
"""
import os
import zipfile
from compiler import compileFile
from os.path import join
from optparse import OptionParser



def build_egg(name):
    py_module = 'update_%s.py' % name

    code = open('update_NAME.py').read()
    code = code.replace('@NAME@', name)
    open(py_module, 'w').write(code)
    compileFile(py_module)

    z = zipfile.ZipFile(join('update_%s-1.0.egg' % name),
                        'w', zipfile.ZIP_DEFLATED)
    for ext in ('', 'c'):
        z.write(py_module + ext)

    data = open('appinst.dat').read()
    data = data.replace('@NAME@', name)
    z.writestr('EGG-INFO/inst/appinst.dat', data)

    z.writestr('EGG-INFO/entry_points.txt',
               '[console_scripts]\n'
               'update-%s = update_%s:main\n' % (name, name))
    z.write('update.ico', 'EGG-INFO/inst/update.ico')
    z.write('update.icns', 'EGG-INFO/inst/update.icns')
    z.close()

    for ext in ('', 'c'):
        os.unlink(py_module + ext)


def main():
    p = OptionParser(usage="usage: %prog [options] NAME",
                     description=__doc__)

    opts, args = p.parse_args()

    if len(args) != 1:
        p.error("exactly one argument expected, try -h")

    build_egg(args[0])


if __name__ == '__main__':
    main()
