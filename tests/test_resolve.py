import unittest
from os.path import abspath, dirname, join

from enstaller.repo.indexed import IndexedRepo
from enstaller.repo.chained import ChainedRepo

from enstaller.resolve import Resolve
import enstaller.indexed_repo.metadata as metadata
import enstaller.indexed_repo.requirement as requirement
from enstaller.indexed_repo.requirement import Req

this_dir = abspath(dirname(__file__))


class DummyRepo(IndexedRepo):

    def __init__(self, index_path, name=None):
        self.index_path = index_path
        self.name = name

    def connect(self, auth=None):
        index_data = open(self.index_path).read()
        self._index = metadata.parse_depend_index(index_data)

    def get(self, key):
        pass


def eggs_rs(c, req_string):
    return c.install_sequence(Req(req_string))


class TestChain0(unittest.TestCase):

    c = Resolve(ChainedRepo([
           DummyRepo(join(this_dir, fn))
           for fn in ['index-add.txt', 'index-5.1.txt', 'index-5.0.txt']]))

    def test_25(self):
        requirement.PY_VER = '2.5'
        self.assertEqual(eggs_rs(self.c, 'SciPy 0.8.0.dev5698'),
                         ['freetype-2.3.7-1.egg', 'libjpeg-7.0-1.egg',
                          'numpy-1.3.0-1.egg', 'PIL-1.1.6-4.egg',
                          'scipy-0.8.0.dev5698-1.egg'])

        self.assertEqual(eggs_rs(self.c, 'SciPy'),
                         ['numpy-1.3.0-1.egg', 'scipy-0.8.0-1.egg'])

        self.assertEqual(eggs_rs(self.c, 'epdcore'),
                         ['AppInst-2.0.4-1.egg', 'numpy-1.3.0-1.egg',
                          'scipy-0.8.0-1.egg', 'EPDCore-1.2.5-1.egg'])

    def test_26(self):
        requirement.PY_VER = '2.6'

        self.assertEqual(eggs_rs(self.c, 'SciPy'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg'])

        self.assertEqual(eggs_rs(self.c, 'epdcore'),
                         ['numpy-1.3.0-2.egg', 'scipy-0.8.0-2.egg',
                          'EPDCore-2.0.0-1.egg'])

class TestChain1(unittest.TestCase):

    cr = ChainedRepo([
            DummyRepo(join(this_dir, name, 'index-7.1.txt'), name)
            for name in ('epd', 'gpl')])
    c = Resolve(cr)

    def test_get_repo(self):
        for req_string, repo_name in [
            ('MySQL_python', 'gpl'),
            ('bitarray', 'epd'),
            ('foobar', None),
            ]:
            egg = self.c.get_egg(Req(req_string))
            if egg is not None:
                self.assertEqual(self.cr.from_which_repo(egg).name,
                                 repo_name)

    def test_get_dist(self):
        requirement.PY_VER = '2.7'
        for req_string, repo_name, egg in [
            ('MySQL_python',  'gpl', 'MySQL_python-1.2.3-2.egg'),
            ('numpy',         'epd', 'numpy-1.6.0-3.egg'),
            ('swig',          'epd', 'swig-1.3.40-2.egg'),
            ('swig 1.3.36',   'epd', 'swig-1.3.36-3.egg'),
            ('swig 1.3.40-1', 'epd', 'swig-1.3.40-1.egg'),
            ('swig 1.3.40-2', 'epd', 'swig-1.3.40-2.egg'),
            ('foobar', None, None),
            ]:
            self.assertEqual(self.c.get_egg(Req(req_string)), egg)
            if egg is not None:
                self.assertEqual(self.cr.from_which_repo(egg).name,
                                 repo_name)

    def test_reqs_dist(self):
        self.assertEqual(self.c.reqs_egg('FiPy-2.1-1.egg'),
                         set([Req('distribute'),
                              Req('scipy'),
                              Req('numpy'),
                              Req('pysparse 1.2.dev203')]))

    def test_root(self):
        self.assertEqual(self.c.install_sequence(Req('numpy 1.5.1'),
                                                 mode='root'),
                         ['numpy-1.5.1-2.egg'])

        self.assertEqual(self.c.install_sequence(Req('numpy 1.5.1-1'),
                                                 mode='root'),
                         ['numpy-1.5.1-1.egg'])

    def test_order1(self):
        self.assertEqual(self.c.install_sequence(Req('numpy')),
                         ['MKL-10.3-1.egg', 'numpy-1.6.0-3.egg'])

    def test_order2(self):
        self.assertEqual(self.c.install_sequence(Req('scipy')),
                         ['MKL-10.3-1.egg', 'numpy-1.5.1-2.egg',
                          'scipy-0.9.0-1.egg'])


class TestChain2(unittest.TestCase):

    cr = ChainedRepo([
            DummyRepo(join(this_dir, name, 'index-7.1.txt'), name)
            for name in ('open', 'runner', 'epd')])
    c = Resolve(cr)

    def test_flat_recur1(self):
        d1 = self.c.install_sequence(Req('openepd'), mode='flat')
        d2 = self.c.install_sequence(Req('openepd'), mode='recur')
        self.assertEqual(d1, d2)
        d3 = self.c.install_sequence(Req('foo'), mode='recur')
        self.assertEqual(d2[:-1], d3[:-1])

    def test_flat_recur2(self):
        for rs in 'epd 7.0', 'epd 7.0-1', 'epd 7.0-2':
            d1 = self.c.install_sequence(Req(rs), mode='flat')
            d2 = self.c.install_sequence(Req(rs), mode='recur')
            self.assertEqual(d1, d2)

    def test_multiple_reqs(self):
        lst = self.c.install_sequence(Req('ets'))
        self.assert_('numpy-1.5.1-2.egg' in lst)
        self.assertEqual(self.cr.from_which_repo('numpy-1.5.1-2.egg').name,
                         'epd')


if __name__ == '__main__':
    unittest.main()
