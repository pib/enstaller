import re
from datetime import datetime, timedelta


time_fmt = '%Y-%m-%d %H:%M:%S'
iso_pat = re.compile(r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}') 
simple_pat = re.compile(r'(\d+)\s*(\w+)$')


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

    if s == 'yesterday':
        s = '1 day'

    m = simple_pat.match(s)
    if m:
        n, unit = m.groups()
        n = int(n)
        unit = unit.rstrip('s')
        if unit == 'week':
            d = timedelta(weeks=n)
        elif unit == 'day':
            d = timedelta(days=n)
        elif unit in ('hour', 'hr'):
            d = timedelta(hour=n)
        elif unit in ('minute', 'min'):
            d = timedelta(minutes=n)
        elif unit in ('second', 'sec'):
            d = timedelta(seconds=n)
        else:
            return None

    print d
    return str(cur - d)[:19]


if __name__ == '__main__':
    ref = datetime(2011, 8, 2, 23, 3, 43)
    print parse(' 200 min ', ref)
