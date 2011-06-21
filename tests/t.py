import sys
from os.path import abspath, dirname

from enstaller.indexed_repo import Chain
from enstaller.indexed_repo.requirement import Req



def show(dists):
    if dists is None:
        print 'none'
        return
    for d in dists:
        print d
    print


c = Chain(verbose=1)
for name in ('runner', 'epd'):
    repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
    c.add_repo(repo, 'index-7.1.txt')


req = Req(' '.join(sys.argv[1:]))
show(c.install_sequence(req, 'flat'))
