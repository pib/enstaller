import re
from datetime import datetime, timedelta


time_fmt = '%Y-%m-%d %H:%M:%S'
iso_pat = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}')


def simple_delta(s):
    pat = re.compile(r'(\d+)\s*(\w+)(?:\s+ago)?$')
    if s == 'yesterday':
        s = '1 day'
    m = pat.match(s)
    if m is None:
        return None
    n = int(m.group(1))
    unit = m.group(2).rstrip('s')
    if unit in ('week', 'wk'):
        return timedelta(weeks=n)
    if unit in ('day', 'd'):
        return timedelta(days=n)
    if unit in ('hour', 'hr'):
        return timedelta(hours=n)
    if unit in ('minute', 'min'):
        return timedelta(minutes=n)
    if unit in ('second', 'sec'):
        return timedelta(seconds=n)
    return None


def parse(s, cur=None):
    """
    parse the string 's' which can be, e.g. '1 hour', '2 weeks',
    and return something like '2011-08-02 23:03:43', or return None, if
    the string could be parsed
    """
    s = s.lower().strip()
    if iso_pat.match(s):
        return s

    if cur is None:
        cur = datetime.now()

    d = simple_delta(s)
    if d is not None:
        return str(cur - d)[:19]

    return None


if __name__ == '__main__':
    ref = datetime(2011, 8, 2, 23, 3, 43)
    print parse(' 35 wk   ', ref)
