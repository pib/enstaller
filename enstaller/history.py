import re
import sys
import time
from os.path import isfile, join
from collections import defaultdict

import egginst


history_path = join(sys.prefix, 'enpkg.hist')


def init():
    if isfile(history_path):
        return
    fo = open(history_path, 'w')
    fo.write(time.strftime("==> %Y-%m-%d %H:%M:%S %Z <==\n"))
    for eggname in egginst.get_installed():
        fo.write('%s\n' % eggname)
    fo.close()


def parse():
    res = defaultdict(set)
    sep_pat = re.compile(r'==>\s*(.+)\s*<==')
    for line in open(history_path):
        line = line.strip()
        if not line:
            continue
        m = sep_pat.match(line)
        if m:
            dt = m.group(1)
            continue
        res[dt].add(line)
    return res


def is_diff(ps):
    return any(p.startswith(('-', '+')) for p in ps)


def read():
    res = []
    raw = parse()
    for dt in sorted(raw):
        inp = raw[dt]
        if is_diff(inp):
            cur -= set(p[1:] for p in inp if p.startswith('-'))
            cur |= set(p[1:] for p in inp if p.startswith('+'))
            print cur, inp
        else:
            cur = inp
        res.append((dt, cur.copy()))            
    return res
        

if __name__ == '__main__':
    for x in read():
        print x
