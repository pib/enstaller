import re
import sys
import time
import bisect
import string
from os.path import isfile, join

import egginst


TIME_FMT = '%Y-%m-%d %H:%M:%S %Z'


def is_diff(cont):
    return any(s.startswith(('-', '+')) for s in cont)


class History(object):
    def __init__(self, prefix=None):
        self.prefix = prefix
        self.path = join(prefix or sys.prefix, 'enpkg.hist')

    def __enter__(self):
        self.init()

    def __exit__(self, exc_type, exc_value, traceback):
        self.update()

    def ensure_path(self):
        if not isfile(self.path):
            sys.exit('Error: log file %r not found' % self.path)

    def get_installed(self):
        return egginst.get_installed(self.prefix)

    def init(self, force=False):
        """
        initialize the history file
        """
        if not force and isfile(self.path):
            return
        fo = open(self.path, 'w')
        fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
        for eggname in self.get_installed():
            fo.write('%s\n' % eggname)
        fo.close()

    def parse(self):
        """
        parse the history file and return a list of
        tuples(datetime strings, set of eggs/diffs)
        """
        self.ensure_path()
        res = []
        sep_pat = re.compile(r'==>\s*(.+?)\s*<==')
        for line in open(self.path):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            m = sep_pat.match(line)
            if m:
                dt = m.group(1)
                res.append((dt, set()))
            else:
                res[-1][1].add(line)
        return res

    def construct_states(self):
        """
        return a list of tuples(datetime strings, set of eggs)
        """
        res = []
        for dt, cont in self.parse():
            if not is_diff(cont):
                cur = cont
            else:
                for s in cont:
                    if s.startswith('-'):
                        cur.discard(s[1:])
                    elif s.startswith('+'):
                        cur.add(s[1:])
                    else:
                        raise Exception('Did not expect: %s' % s)
            res.append((dt, cur.copy()))
        return res

    def find_revision(self, times, dt):
        """
        given a list of (sorted) datetimes 'times', return the index
        corresponding to the time 'dt'
        """
        i = bisect.bisect(times, dt)
        if i == 0:
            return 0
        else:
            return i - 1

    def get_state(self, arg=None):
        """
        return the state, i.e. the set of eggs, for a given revision or time,
        defaults to latest
        """
        times, pkgs = zip(*self.construct_states())
        if arg is None:
            i = -1
        elif isinstance(arg, str):
            i = self.find_revision(times, arg)
        elif isinstance(arg, int):
            i = arg
        else:
            raise Exception('Did not expect: %r' % arg)
        return pkgs[i]

    def update(self):
        """
        update the history file (creating a new one if necessary)
        """
        self.init()
        last = self.get_state()
        curr = set(self.get_installed())
        if last == curr:
            return
        fo = open(self.path, 'a')
        fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
        for fn in last - curr:
            fo.write('-%s\n' % fn)
        for fn in curr - last:
            fo.write('+%s\n' % fn)
        fo.close()

    def print_diff(self, diff):
        added = {}
        removed = {}
        for s in diff:
            fn = s[1:]
            name, version = egginst.name_version_fn(fn)
            if s.startswith('-'):
                removed[name.lower()] = version
            elif s.startswith('+'):
                added[name.lower()] = version
        changed = set(added) & set(removed)
        for name in sorted(changed):
            print '     %s  (%s -> %s)' % (name, removed[name], added[name])
        for name in sorted(set(removed) - changed):
            print '    -%s-%s' % (name, removed[name])
        for name in sorted(set(added) - changed):
            print '    +%s-%s' % (name, added[name])

    def print_log(self):
        self.ensure_path()
        for i, (dt, cont) in enumerate(self.parse()):
            print '%s  (rev %d)' % (dt, i)
            if is_diff(cont):
                self.print_diff(cont)
            else:
                for x in sorted(cont, key=string.lower):
                    print '    %s' % x
            print


if __name__ == '__main__':
    h = History()
    with h:
        h.update()
        h.print_log()
