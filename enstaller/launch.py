import re
import sys
import subprocess
from os.path import isfile, join

from enpkg import Enpkg


class Launch(Enpkg):

    def get_icon_path(self, egg):
        info = self.find(egg)
        if 'app_icon' in info:
            path = join(info['meta_dir'], info['app_icon'])
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

    def registry_path_list(self, egg):
        if not self.hook:
            return []
        info = self.find(egg)
        pat = re.compile(r'([\w.]+)\s+([\w.]+)-(\d+)$')
        result = []
        for rs in ['%(name)s %(version)s-%(build)d' % info] + info['packages']:
            m = pat.match(rs)
            if not m:
                print "Warning: not a full requirement: %r" % rs
                continue
            d = self.find(m.expand(r'\1-\2-\3.egg'))
            if not d:
                print "Warning: cannot find install for: %r" % rs
                continue
            path = join(d['meta_dir'], 'registry.txt')
            if not isfile(path):
                print "Warning: no registry file:", path
                continue
            result.append(path)
        return result


if __name__ == '__main__':
    x = Launch(['/home/ischnell/eggs'],
               prefixes=['/home/ischnell/jpm/Python-2.7', sys.prefix],
               hook=1,
               verbose=1)
#    for k, info in x.query():#app=True):
#        print k, info.get('installed')
    fn = 'nose-1.1.2-1.egg'
    #x.install(fn, force=1)
    #print x.get_icon_path(fn)
    #x.launch_app(fn)
    for p in x.registry_path_list(fn):
        print p
