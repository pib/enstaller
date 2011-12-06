import sys
import json
import subprocess
from glob import glob
from os.path import abspath, isfile, join

from egg_meta import split_eggname

from enpkg import Enpkg


class Launch(Enpkg):

    def get_installed_apps(self):
        for p in glob(join(self.pkgs_dir, '*', 'EGG-INFO', 'app_meta.json')):
            info = json.load(open(p))
            info['installed'] = True
            yield info['key'], info

    def get_all_apps(self):
        self._connect()
        d = dict(self.remote.query(app=True))
        d.update(self.get_installed_apps())
        return d

    def get_icon_path(self, egg):
        info = self.info_installed_app(egg)
        if 'app_icon' in info:
            path = abspath(join(self.egginfo_dir_egg(egg), info['app_icon']))
            if isfile(path):
                return path
        return None

    def launch_app(self, egg):
        info = self.info_installed_app(egg)
        if 'app_cmd' in info:
            cmd = info['app_cmd']
        elif 'app_entry' in info:
            cmd = [sys.executable,
                   join(self.egginfo_dir_egg(egg), 'app_entry.py')]
        else:
            raise Exception("Don't know what to launch for egg: %r" % egg)
        if 'app_args' in info:
            cmd.extend(info['app_args'])
        subprocess.call(cmd)

    def install_app(self, egg, force=False):
        self.install_recur(egg, True, force)

    def info_installed_app(self, egg):
        meta_path = join(self.egginfo_dir_egg(egg), 'app_meta.json')
        info = json.load(open(meta_path))
        info['installed'] = True
        return info

    # --------------------------------------------------------------

    def registry_path_egg(self, egg):
        return join(self.egginfo_dir_egg(egg), 'registry.txt')

    def egginfo_dir_egg(self, egg):
        return join(self.versioned_dir_egg(egg), 'EGG-INFO')

    def versioned_dir_egg(self, egg):
        n, v, b = split_eggname(egg)
        return join(self.pkgs_dir, '%s-%s-%d' % (n.lower(), v, b))


if __name__ == '__main__':
    #x = Launch(rem, prefix=prefix)#, verbose=1)
    x = Launch(['/home/ischnell/eggs/'], verbose=1)
    fn = 'nose-1.1.2-1.egg'
    #x.install('enstaller-4.5.0-1.egg')
    #x.remove('enstaller-4.5.0-1.egg')
    #x.install_app(fn, force=1)
    for k, info in x.get_all_apps().iteritems():
        print k, x.get_icon_path(k)
    x.launch_app(fn)
    #print dict(rem.query(app=True))
    #print x.get_icon_path(fn)
