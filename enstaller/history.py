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

def pretty_diff(diff):
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
        yield ' %s  (%s -> %s)' % (name, removed[name], added[name])
    for name in sorted(set(removed) - changed):
        yield '-%s-%s' % (name, removed[name])
    for name in sorted(set(added) - changed):
        yield '+%s-%s' % (name, added[name])

def pretty_cont(cont):
    if is_diff(cont):
        return pretty_diff(cont)
    else:
        return iter(sorted(cont, key=string.lower))

def find_revision(times, dt):
    """
    given a list of (sorted) datetimes 'times', return the index
    corresponding to the time 'dt'
    """
    i = bisect.bisect(times, dt)
    if i == 0:
        return 0
    else:
        return i - 1


class History(object):

    def __init__(self, prefix):
        self.prefix = prefix
        if prefix is None:
            return
        self._log_path = join(prefix, 'enpkg.hist')

    def __enter__(self):
        if self.prefix is None:
            return
        self.update()

    def __exit__(self, exc_type, exc_value, traceback):
        if self.prefix is None:
            return
        self.update()

    def _init_log_file(self, force=False):
        """
        initialize the log file
        """
        if not force and isfile(self._log_path):
            return
        fo = open(self._log_path, 'w')
        fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
        for eggname in egginst.get_installed(self.prefix):
            fo.write('%s\n' % eggname)
        fo.close()

    def update(self):
        """
        update the history file (creating a new one if necessary)
        """
        self._init_log_file()
        last = self.get_state()
        curr = set(egginst.get_installed(self.prefix))
        if last == curr:
            return
        fo = open(self._log_path, 'a')
        fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
        for fn in last - curr:
            fo.write('-%s\n' % fn)
        for fn in curr - last:
            fo.write('+%s\n' % fn)
        fo.close()

    def parse(self):
        """
        parse the history file and return a list of
        tuples(datetime strings, set of eggs/diffs)
        """
        res = []
        sep_pat = re.compile(r'==>\s*(.+?)\s*<==')
        for line in open(self._log_path):
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

    def get_state(self, arg=None):
        """
        return the state, i.e. the set of eggs, for a given revision or time,
        defaults to latest (which is the same as the current state when the
        log file is up-to-date)
        """
        times, pkgs = zip(*self.construct_states())
        if arg is None:
            i = -1
        elif isinstance(arg, str):
            i = find_revision(times, arg)
        elif isinstance(arg, int):
            i = arg
        else:
            raise Exception('Did not expect: %r' % arg)
        return pkgs[i]

    def print_log(self):
        for i, (dt, cont) in enumerate(self.parse()):
            print '%s  (rev %d)' % (dt, i)
            for line in pretty_cont(cont):
                print '    %s' % line
            print


if __name__ == '__main__':
    h = History(sys.prefix)
    with h:
        h.update()
        h.print_log()
