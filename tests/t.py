from os.path import abspath, dirname

from enstaller.indexed_repo import Chain
from enstaller.indexed_repo.requirement import Req



c = Chain(verbose=1)

for name in ('open', 'runner', 'epd'):
    repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
    c.add_repo(repo, 'index-7.1.txt')


for dist in c.install_order(Req('openepd'), recur=True):
    print dist
