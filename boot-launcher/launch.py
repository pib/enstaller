import re
import os
import sys
import subprocess
import shutil
import zipfile
from os.path import dirname, expanduser, isdir, isfile, join
from optparse import OptionParser


verbose = False
eggs_dir = local_repo = prefix = pkgs_dir = python_exe = None


def unzip(zip_path, dir_path):
    """
    unpack the zip file into dir_path, creating directories as required
    """
    print "Unzipping: %r" % zip_path
    print "     into: %r" % dir_path
    z = zipfile.ZipFile(zip_path)
    for name in z.namelist():
        if name.endswith('/') or name.startswith('.unused'):
            continue
        path = join(dir_path, *name.split('/'))
        dpath = dirname(path)
        if not isdir(dpath):
            os.makedirs(dpath)
        fo = open(path, 'wb')
        fo.write(z.read(name))
        fo.close()
    z.close()


def parse_dists_file(path):
    pat = re.compile(r'(([+-]{2})\s*)?(\w\S+\.egg)$')
    for line in open(path):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = pat.match(line)
        if m is None:
            sys.exit('Error: invalid line in dists.txt: %r' % line)
        yield m.group(3)


def registry_egg(egg):
    return join(pkgs_dir, egg[:-4], 'EGG-INFO', 'registry.txt')


def cp_to_repo(egg, force=False):
    path = join(local_repo, egg)
    if not isfile(path) or force:
        shutil.copyfile(join(eggs_dir, egg), path)
    return path


def bootstrap_enstaller(egg):
    assert egg.startswith('enstaller-')
    code = ("import sys;"
            "sys.path.insert(0, %r);"
            "from egginst.bootstrap import main;"
            "main()" % cp_to_repo(egg))
    subprocess.check_call([python_exe, '-c', code])


def update_eggs(eggs):
    if not isdir(local_repo):
        os.makedirs(local_repo)

    if not isfile(python_exe):
        unzip(cp_to_repo(eggs[0]), prefix)

    if not isfile(registry_egg(eggs[1])):
        bootstrap_enstaller(eggs[1])

    if sys.platform == 'win32':
        egginst_py = join(prefix, r'Scripts\egginst-script.py')
    else:
        egginst_py = join(prefix, 'bin/egginst')

    for egg in eggs[1:]:
        if isfile(registry_egg(egg)):
            continue
        subprocess.check_call([python_exe, egginst_py, '--hook',
                               '--pkgs-dir', pkgs_dir,
                               cp_to_repo(egg)])


def main():
    if sys.platform == 'win32' and not sys.executable.endswith('python.exe'):
        default_eggs_dir = dirname(sys.executable)
    else:
        default_eggs_dir = os.getcwd()


    p = OptionParser(usage="usage: %prog [options]",
                     description=__doc__)

    p.add_option("--root",
                 action="store",
                 default=join(expanduser('~'), 'canopy'),
                 help="install location, defaults to %default",
                 metavar='PATH')

    p.add_option("--eggs-dir",
                 action="store",
                 default=default_eggs_dir,
                 help="directory with eggs to install (and dists.txt), "
                      "defaults to %default",
                 metavar='PATH')

    p.add_option('-v', "--verbose", action="store_true")

    opts, args = p.parse_args()

    if args:
        p.error('no argument expected, try -h')

    global verbose, eggs_dir, local_repo, prefix, pkgs_dir, python_exe

    eggs_dir = opts.eggs_dir
    verbose = opts.verbose

    if verbose:
        print "eggs_dir = %r" % eggs_dir

    eggs = list(parse_dists_file(join(eggs_dir, 'dists.txt')))

    if verbose:
        for egg in eggs:
            print "\t" + egg

    local_repo = join(opts.root, 'repo')
    prefix = join(opts.root, eggs[0][:-4])
    pkgs_dir = join(prefix, 'pkgs')
    if sys.platform == 'win32':
        python_exe = join(prefix, 'python.exe')
    else:
        python_exe = join(prefix, 'bin', 'python')

    if verbose:
        print "local_repo = %r" % local_repo
        print "prefix = %r" % prefix
        print "python_exe = %r" % python_exe

    update_eggs(eggs)

    entry_py = join(dirname(registry_egg(eggs[-1])), 'app_entry.py')
    return subprocess.call([python_exe, entry_py])


if __name__ == '__main__':
    sys.exit(main())
