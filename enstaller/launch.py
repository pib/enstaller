import sys
import json
import subprocess
from glob import glob
from os.path import abspath, isfile, join

from egg_meta import split_eggname

from enpkg import Enpkg


class Launch(Enpkg):

    def query_installed_apps(self, **kwargs):
        kwargs['app'] = True
        return self.query_installed(**kwargs)

    def query_all_apps(self, **kwargs):
        kwargs['app'] = True
        d = dict(self.query_remote(**kwargs))
        d.update(self.query_installed_apps(**kwargs))
        return d

    def get_icon_path(self, egg):
        info = self.find(egg)
        if 'app_icon' in info:
            path = abspath(join(info['meta_dir'], info['app_icon']))
            if isfile(path):
                return path
        return None

    def launch_app(self, egg):
        info = self.find(egg)
        if 'app_cmd' in info:
            cmd = info['app_cmd']
        elif 'app_entry' in info:
            cmd = [sys.executable, join(info['meta_dir'], 'app_entry.py')]
        else:
            raise Exception("Don't know what to launch for egg: %r" % egg)
        if 'app_args' in info:
            cmd.extend(info['app_args'])
        subprocess.call(cmd)


if __name__ == '__main__':
    #x = Launch(['/home/ischnell/eggs/'], verbose=1)
    x = Launch(['/Users/ischnell/repo/'],
               prefixes=['/Users/ischnell/jpm/Python-2.7'], hook=1,
               verbose=1)
    fn = 'nose-1.1.2-1.egg'
    #x.install('enstaller-4.5.0-1.egg')
    #x.remove('enstaller-4.5.0-1.egg')
    x.install(fn, force=1)
    for k, info in x.query_all_apps().iteritems():
        print k, x.get_icon_path(k)
    x.launch_app(fn)
    #print x.get_icon_path(fn)
