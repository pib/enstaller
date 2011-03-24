import zipfile
from compiler import compileFile
from os.path import join



def build_egg(name):
    py_module = 'update_%s.py' % name

    compileFile(py_module)
    z = zipfile.ZipFile(join('update_%s-1.0.egg' % name),
                        'w', zipfile.ZIP_DEFLATED)
    z.write('appinst.dat', 'EGG-INFO/inst/appinst.dat')
    z.write('update.ico', 'EGG-INFO/inst/update.ico')
    for ext in ('', 'c'):
        z.write(py_module + ext)
    z.writestr('EGG-INFO/entry_points.txt', '''\
[console_scripts]
update-%s = update_$s:main
    ''' % (name, name))

    z.close()


if __name__ == '__main__':
    build_egg('foo')
