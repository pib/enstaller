import re
import sys
import time
from os.path import isfile, join
from collections import defaultdict

import egginst


PATH = join(sys.prefix, 'enpkg.hist')


def write_time(fo):
    fo.write(time.strftime("==> %Y-%m-%d %H:%M:%S %Z <==\n"))


def init():
    if isfile(PATH):
        return
    fo = open(PATH, 'w')
    write_time(fo)
    for eggname in egginst.get_installed():
        fo.write('%s\n' % eggname)
    fo.close()


def parse():
    res = defaultdict(set)
    sep_pat = re.compile(r'==>\s*(.+)\s*<==')
    for line in open(PATH):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        m = sep_pat.match(line)
        if m:
            dt = m.group(1)
            continue
        res[dt].add(line)
    return res


def read():
    res = []
    raw = parse()
    for dt in sorted(raw):
        inp = raw[dt]
        if any(p.startswith(('-', '+')) for p in inp):
            for p in inp:
                if p.startswith('-'):
                    cur.discard(p[1:])
                elif p.startswith('+'):
                    cur.add(p[1:])
                else:
                    raise Exception('Did not expect: %s' % p)
        else:
            cur = inp
        res.append((dt, cur.copy()))
    return res


def update():
    init()
    dummy, last = read()[-1]
    curr = set(egginst.get_installed())
    if last == curr:
        return
    fo = open(PATH, 'a') 
    write_time(fo)
    for fn in last - curr:
        fo.write('-%s\n' % fn)
    for fn in curr - last:
        fo.write('+%s\n' % fn)
    fo.close()


if __name__ == '__main__':
    #init()
    #for x in read():
    #    print x
    update()
