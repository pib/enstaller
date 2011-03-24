import os
import zipfile
from compiler import compileFile
from os.path import join


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
    z.close()

    for ext in ('', 'c'):
        os.unlink(py_module + ext)


if __name__ == '__main__':
    build_egg('foo')
