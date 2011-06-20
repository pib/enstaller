from os.path import abspath, dirname

from enstaller.indexed_repo import Chain
from enstaller.indexed_repo.requirement import Req



c = Chain(verbose=1)

for name in ('open', 'runner', 'epd'):
    repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
    c.add_repo(repo, 'index-7.1.txt')


def show(dists):
    for d in dists:
        print d
    print


a = c.order(Req('openepd'), mode='flat')
show(a)

b = c.order(Req('openepd'), mode='recur')
show(b)

assert a == b

c = c.order(Req('foo'), mode='recur')
show(c)

assert b[:-1] == c[:-1]
