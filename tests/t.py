import sys
from os.path import abspath, dirname

from enstaller.indexed_repo import Chain
from enstaller.indexed_repo.requirement import Req



c = Chain(verbose=0)
for name in ('open', 'runner', 'epd'):
    repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
    c.add_repo(repo, 'index-7.1.txt')


def show(dists):
    for d in dists:
        print d
    print


d1 = c.order(Req('openepd'), mode='flat')
#show(d1)
d2 = c.order(Req('openepd'), mode='recur')
#show(d2)
assert d1 == d2
d3 = c.order(Req('foo'), mode='recur')
#show(d3)
assert d2[:-1] == d3[:-1]


c = Chain(verbose=1)
for name in ('runner', 'epd'):
    repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
    c.add_repo(repo, 'index-7.1.txt')

for rs in 'epd 7.0', 'epd 7.0-1', 'epd 7.0-2':
    d1 = c.order(Req(rs), mode='flat')
    d2 = c.order(Req(rs), mode='recur')
    assert d1 == d2

req = Req(' '.join(sys.argv[1:]))
show(c.order(req))
