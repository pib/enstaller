import re
import sys
import subprocess
from os.path import isfile, join

from enpkg import Enpkg


class Launch(Enpkg):

    def get_icon(self, egg):
        info = self.find(egg)
        if info and 'app_icon' in info:
            path = join(info['meta_dir'], info['app_icon'])
            if isfile(path):
                return open(path, 'rb').read()
        else:
            # Egg not installed, see if there is one in the store
            return self.remote.get_metadata(egg)['app_icon'].decode('base64')
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
        if sys.platform == 'win32':
            DETACHED_PROCESS = 0x00000008
            subprocess.Popen(cmd, creationflags=DETACHED_FLAGS)
        else:
            subprocess.Popen(cmd)

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
    from enpkg import create_joined_store
    from plat import subdir

    urls = ['http://www.enthought.com/repo/.jpm/%s/' % subdir]

    remote = create_joined_store(urls)
    x = Launch(remote,
               #prefixes=['/home/ischnell/jpm/Python-2.7', sys.prefix],
               hook=1, verbose=1)

    fn = 'test-1.0-1.egg'

    x.install(fn)#, forceall=1)
    for k, info in x.query(app=True):
        print k
        if info.get('installed'):
            print '\t', x.get_icon(k)
    print x.get_icon(fn)
    x.launch_app(fn)
