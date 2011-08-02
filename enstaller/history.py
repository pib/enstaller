import re
import sys
import time
import bisect
from os.path import isfile, join
from collections import defaultdict

import egginst


PATH = join(sys.prefix, 'enpkg.hist')
TIME_FMT = '%Y-%m-%d %H:%M:%S %Z'


def init(force=False):
    """
    initialize the history file
    """
    if not force and isfile(PATH):
        return
    fo = open(PATH, 'w')
    fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
    for eggname in egginst.get_installed():
        fo.write('%s\n' % eggname)
    fo.close()


def parse():
    """
    parse the history file and return a list of
    tuples(datetime strings, set of eggs/diffs)
    """
    res = []
    sep_pat = re.compile(r'==>\s*(.+?)\s*<==')
    for line in open(PATH):
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


def construct_states():
    """
    return a list of tuples(datetime strings, set of eggs)
    """
    res = []
    for dt, cont in parse():
        if any(s.startswith(('-', '+')) for s in cont):
            for s in cont:
                if s.startswith('-'):
                    cur.discard(s[1:])
                elif s.startswith('+'):
                    cur.add(s[1:])
                else:
                    raise Exception('Did not expect: %s' % s)
        else:
            cur = cont
        res.append((dt, cur.copy()))

    # make sure times are sorted
    times = [dt for dt, pkgs in res]
    assert times == sorted(times)

    return res


def find_revision(times, dt=None):
    """
    given a list of (sorted) datetimes 'times', return the index corresponding
    to the time 'dt'
    """
    if dt is None:
        dt = time.strftime(TIME_FMT)
    i = bisect.bisect(times, dt)
    if i > 0:
        i -= 1
    return i


def get_state(arg=None):
    """
    return the state, i.e. the set of eggs, for a given revision or time,
    defaults to latest
    """
    times, pkgs = zip(*construct_states())
    if arg is None:
        i = -1
    elif isinstance(arg, str):
        i = find_revision(times, arg)
    elif isinstance(arg, int):
        i = arg
    else:
        raise Exception('Did not expect: %r' % arg)
    return pkgs[i]


def update():
    init()
    last = get_state()
    curr = set(egginst.get_installed())
    if last == curr:
        return
    fo = open(PATH, 'a')
    fo.write(time.strftime("==> %s <==\n" % TIME_FMT))
    for fn in last - curr:
        fo.write('-%s\n' % fn)
    for fn in curr - last:
        fo.write('+%s\n' % fn)
    fo.close()


def print_log():
    for i, (dt, cont) in enumerate(parse()):
        print '%s (rev %d)' % (dt, i)
        for x in cont:
            print '    %s' % x


if __name__ == '__main__':
    #init()
    #update()
    print_log()
