import sys
import subprocess
from os.path import abspath, isfile, join

from enpkg import Enpkg


class Launch(Enpkg):

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
    for k, info in x.query(app=True):
        print k, info.get('installed')
    fn = 'nose-1.1.2-1.egg'
    x.install(fn, force=1)
    x.launch_app(fn)
    #print x.get_icon_path(fn)
