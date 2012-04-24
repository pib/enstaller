# Author: Ilan Schnell <ischnell@enthought.com>
"""\
egginst is a simple tool for installing and uninstalling eggs.  The tool
is brain dead in the sense that it does not care if the eggs it installs
are for the correct platform, it's dependencies got installed, another
package needs to be uninstalled prior to the install, and so on.  Those tasks
are responsibilities of a package manager, e.g. enpkg.  You just give it
eggs and it installs/uninstalls them.
"""
import os
import sys
import re
import json
import zipfile
from uuid import uuid4
from os.path import abspath, basename, dirname, join, isdir, isfile

from utils import (on_win, bin_dir_name, rel_site_packages, human_bytes,
                   rm_empty_dir, rm_rf, get_executable)
import scripts


NS_PKG_PAT = re.compile(
    r'\s*__import__\([\'"]pkg_resources[\'"]\)\.declare_namespace'
    r'\(__name__\)\s*$')


def name_version_fn(fn):
    """
    Given the filename of a package, returns a tuple(name, version).
    """
    if fn.endswith('.egg'):
        fn = fn[:-4]
    if '-' in fn:
        return tuple(fn.split('-', 1))
    else:
        return fn, ''


class EggInst(object):

    def __init__(self, path, prefix=sys.prefix,
                 hook=False, pkgs_dir=None, evt_mgr=None,
                 verbose=False, noapp=False):
        self.path = path
        self.fn = basename(path)
        name, version = name_version_fn(self.fn)
        self.cname = name.lower()
        self.prefix = abspath(prefix)
        self.hook = bool(hook)
        self.evt_mgr = evt_mgr
        self.noapp = noapp

        self.bin_dir = join(self.prefix, bin_dir_name)

        if self.prefix != abspath(sys.prefix):
            scripts.executable = get_executable(self.prefix)

        if self.hook:
            if pkgs_dir:
                self.pkgs_dir = abspath(pkgs_dir)
            else:
                self.pkgs_dir = join(self.prefix, 'pkgs')
            self.pkg_dir = join(self.pkgs_dir, self.cname + '-' + version)
            self.pyloc = self.pkg_dir
            self.meta_dir = join(self.pkg_dir, 'EGG-INFO')
            self.registry_txt = join(self.meta_dir, 'registry.txt')
        else:
            self.site_packages = join(self.prefix, rel_site_packages)
            self.pyloc = self.site_packages
            self.egginfo_dir = join(self.prefix, 'EGG-INFO')
            self.meta_dir = join(self.egginfo_dir, self.cname)

        self.meta_json = join(self.meta_dir, 'egginst.json')
        self.files = []
        self.verbose = verbose


    def install(self, extra_info=None):
        if not isdir(self.meta_dir):
            os.makedirs(self.meta_dir)

        self.z = zipfile.ZipFile(self.path)
        self.arcnames = self.z.namelist()
        self.extract()

        if on_win:
            scripts.create_proxies(self)
        else:
            import links
            import object_code
            if self.verbose:
                links.verbose = object_code.verbose = True
            links.create(self)
            object_code.fix_files(self)

        if not self.hook:
            self.entry_points()
        if ('EGG-INFO/spec/depend' in self.arcnames  or
            'EGG-INFO/info.json' in self.arcnames):
            import eggmeta
            info = eggmeta.create_info(self, extra_info)
        else:
            info = {}
        self.z.close()

        if not self.hook:
            scripts.fix_scripts(self)
            self.install_app()
        self.write_meta()

        if self.hook:
            import registry
            registry.create_file(self)

        if info.get('app'):
            import app_entry
            app_entry.create_entry(self, info)

        self.run('post_egginst.py')


    def entry_points(self):
        lines = list(self.lines_from_arcname('EGG-INFO/entry_points.txt',
                                             ignore_empty=False))
        if lines == []:
            return
        import ConfigParser, cStringIO
        conf = ConfigParser.ConfigParser()
        conf.readfp(cStringIO.StringIO('\n'.join(lines) + '\n'))
        if ('console_scripts' in conf.sections() or
                'gui_scripts' in conf.sections()):
            if self.verbose:
                print 'creating scripts'
                scripts.verbose = True
            scripts.create(self, conf)


    def rel_prefix(self, path):
        return abspath(path).replace(self.prefix, '.').replace('\\', '/')

    def write_meta(self):
        d = dict(
            egg_name = self.fn,
            prefix = self.prefix,
            installed_size = self.installed_size,
            files = [self.rel_prefix(p)
                           if abspath(p).startswith(self.prefix) else p
                     for p in self.files + [self.meta_json]]
        )
        with open(self.meta_json, 'w') as f:
            json.dump(d, f, indent=2, sort_keys=True)

    def read_meta(self):
        d = read_meta(self.meta_dir)
        self.installed_size = d['installed_size']
        self.files = [join(self.prefix, f) for f in d['files']]


    def lines_from_arcname(self, arcname, ignore_empty=True):
        if not arcname in self.arcnames:
            return
        for line in self.z.read(arcname).splitlines():
            line = line.strip()
            if ignore_empty and line == '':
                continue
            if line.startswith('#'):
                continue
            yield line


    def extract(self):
        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from console import ProgressManager

        n = 0
        size = sum(self.z.getinfo(name).file_size for name in self.arcnames)
        self.installed_size = size
        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="installing egg",
                steps=size,
                # ---
                progress_type="installing", filename=self.fn,
                disp_amount=human_bytes(self.installed_size),
                super_id=getattr(self, 'super_id', None))
        with progress:
            for name in self.arcnames:
                n += self.z.getinfo(name).file_size
                self.write_arcname(name)
                progress(step=n)


    def get_dst(self, arcname):
        if (not self.hook and arcname == 'EGG-INFO/PKG-INFO' and
                      self.path.endswith('.egg')):
            return join(self.site_packages, self.fn + '-info')

        for start, cond, dst_dir in [
            ('EGG-INFO/prefix/',  True,       self.prefix),
            ('EGG-INFO/usr/',     not on_win, self.prefix),
            ('EGG-INFO/scripts/', True,       self.bin_dir),
            ('EGG-INFO/',         True,       self.meta_dir),
            ('',                  True,       self.pyloc),
            ]:
            if arcname.startswith(start) and cond:
                return abspath(join(dst_dir, arcname[len(start):]))
        raise Exception("Didn't expect to get here")

    py_pat = re.compile(r'^(.+)\.py(c|o)?$')
    so_pat = re.compile(r'^lib.+\.so')
    py_obj = '.pyd' if on_win else '.so'
    def write_arcname(self, arcname):
        if arcname.endswith('/') or arcname.startswith('.unused'):
            return
        m = self.py_pat.match(arcname)
        if m and (m.group(1) + self.py_obj) in self.arcnames:
            # .py, .pyc, .pyo next to .so are not written
            return
        path = self.get_dst(arcname)
        dn, fn = os.path.split(path)
        data = self.z.read(arcname)
        if fn in ['__init__.py', '__init__.pyc']:
            tmp = arcname.rstrip('c')
            if tmp in self.arcnames and NS_PKG_PAT.match(self.z.read(tmp)):
                if fn == '__init__.py':
                    data = ''
                if fn == '__init__.pyc':
                    return
        self.files.append(path)
        if not isdir(dn):
            os.makedirs(dn)
        rm_rf(path)
        fo = open(path, 'wb')
        fo.write(data)
        fo.close()
        if (arcname.startswith(('EGG-INFO/usr/bin/', 'EGG-INFO/scripts/')) or
                fn.endswith(('.dylib', '.pyd', '.so')) or
                (arcname.startswith('EGG-INFO/usr/lib/') and
                 self.so_pat.match(fn))):
            os.chmod(path, 0755)


    def install_app(self, remove=False):
        if self.noapp:
            return

        path = join(self.meta_dir, 'inst', 'appinst.dat')
        if not isfile(path):
            return

        try:
            import appinst
        except ImportError:
            return

        try:
            if remove:
                appinst.uninstall_from_dat(path)
            else:
                appinst.install_from_dat(path)
        except Exception, e:
            print("Warning (%sinstalling application item):\n%r" %
                  ('un' if remove else '', e))


    def run(self, fn):
        path = join(self.meta_dir, fn)
        if not isfile(path):
            return
        from subprocess import call
        call([sys.executable, '-E', path, '--prefix', self.prefix],
             cwd=dirname(path))


    def rm_dirs(self):
        dir_paths = set()
        len_prefix = len(self.prefix)
        for path in set(dirname(p) for p in self.files):
            while len(path) > len_prefix:
                dir_paths.add(path)
                path = dirname(path)

        for path in sorted(dir_paths, key=len, reverse=True):
            rm_empty_dir(path)

    def remove(self):
        if not isdir(self.meta_dir):
            print "Error: Can't find meta data for:", self.cname
            return

        if self.evt_mgr:
            from encore.events.api import ProgressManager
        else:
            from console import ProgressManager

        self.read_meta()
        n = 0
        progress = ProgressManager(
                self.evt_mgr, source=self,
                operation_id=uuid4(),
                message="removing egg",
                steps=len(self.files),
                # ---
                progress_type="removing", filename=self.fn,
                disp_amount=human_bytes(self.installed_size),
                super_id=getattr(self, 'super_id', None))
        self.install_app(remove=True)
        self.run('pre_egguninst.py')

        with progress:
            for p in self.files:
                n += 1
                progress(step=n)

                if self.hook and not p.startswith(self.pkgs_dir):
                    continue

                rm_rf(p)
                if p.endswith('.py'):
                    rm_rf(p + 'c')
            self.rm_dirs()
            rm_rf(self.meta_dir)
            if self.hook:
                rm_empty_dir(self.pkg_dir)
            else:
                rm_empty_dir(self.egginfo_dir)


def read_meta(meta_dir):
    meta_json = join(meta_dir, 'egginst.json')
    if isfile(meta_json):
        return json.load(open(meta_json))
    return None


def get_installed(prefix=sys.prefix):
    """
    Generator returns a sorted list of all installed packages.
    Each element is the filename of the egg which was used to install the
    package.
    """
    egg_info_dir = join(prefix, 'EGG-INFO')
    if not isdir(egg_info_dir):
        return
    pat = re.compile(r'([a-z0-9_.]+)$')
    for fn in sorted(os.listdir(egg_info_dir)):
        if not pat.match(fn):
            continue
        d = read_meta(join(egg_info_dir, fn))
        if d is None:
            continue
        yield d['egg_name']


def print_installed(prefix=sys.prefix):
    fmt = '%-20s %s'
    print fmt % ('Project name', 'Version')
    print 40 * '='
    for fn in get_installed(prefix):
        print fmt % name_version_fn(fn)


def main():
    from optparse import OptionParser

    p = OptionParser(usage="usage: %prog [options] [EGGS ...]",
                     description=__doc__)

    p.add_option('-l', "--list",
                 action="store_true",
                 help="list all installed packages")

    p.add_option("--noapp",
                 action="store_true",
                 help="don't install/remove application menu items")

    p.add_option("--prefix",
                 action="store",
                 default=sys.prefix,
                 help="install prefix, defaults to %default",
                 metavar='PATH')

    p.add_option("--hook",
                 action="store_true",
                 help="don't install into site-packages (experimental)",
                 metavar='PATH')

    p.add_option("--pkgs-dir",
                 action="store",
                 help="packages directories (works only with --hook)",
                 metavar='PATH')

    p.add_option('-r', "--remove",
                 action="store_true",
                 help="remove package(s), requires the egg or project name(s)")

    p.add_option('-v', "--verbose", action="store_true")
    p.add_option('--version', action="store_true")

    opts, args = p.parse_args()
    if opts.version:
        from enstaller import __version__
        print "enstaller version:", __version__
        return

    prefix = abspath(opts.prefix)

    if opts.list:
        if args:
            p.error("the --list option takes no arguments")
        print_installed(prefix)
        return

    if 0:
        from encore.events.api import EventManager
        from encore.terminal.api import ProgressDisplay
        evt_mgr = EventManager()
        display = ProgressDisplay(evt_mgr)
    else:
        evt_mgr = None

    for path in args:
        ei = EggInst(path, prefix, opts.hook, opts.pkgs_dir, evt_mgr,
                     verbose=opts.verbose, noapp=opts.noapp)
        if opts.remove:
            ei.remove()
        else: # default is always install
            ei.install()


if __name__ == '__main__':
    main()
