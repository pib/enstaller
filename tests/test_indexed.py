import sys
import unittest
from os.path import abspath, dirname

from enstaller.indexed_repo import Chain
import enstaller.indexed_repo.dist_naming as dist_naming
import enstaller.indexed_repo.requirement as requirement
from enstaller.indexed_repo.requirement import (Req, dist_as_req,
                                                add_Reqs_to_spec)


class TestDistNaming(unittest.TestCase):

    def test_split_dist(self):
        for repo, fn in [
            ('http://www.example.com/repo/', 'foo.egg'),
            ('https://www.example.com/repo/', 'foo.egg'),
            ('file:///home/repo/', 'numpy-1.1.1-5.egg'),
            ('file://E:\\eggs\\', 'numpy-1.1.1-5.egg'),
            ('file://C:\\Desk and Top\\', 'with space.egg'),
            ]:
            dist = repo + fn
            self.assertEqual(dist_naming.split_dist(dist), (repo, fn))

        for dist in ['local:/foo.egg', '', 'foo.egg', 'file:///usr/']:
            self.assertRaises(AssertionError, dist_naming.split_dist, dist)

    def test_is_valid_eggname(self):
        for fn, valid in [
            ('numpy-1.3.4-7.egg', True),
            ('numpy-1.3.4n7-py2.5.egg', False),
            ('numpy-1.3.4-172.egg', True),
            ('numpy-1.3.4-py2.5-win32.egg', False),
            ]:
            self.assertEqual(dist_naming.is_valid_eggname(fn), valid)

    def test_split_eggname(self):
        for fn, nvb in [
            ('numpy-1.3.4-7.egg', ('numpy', '1.3.4', 7)),
            ('python_dateutil-0.5-12.egg', ('python_dateutil', '0.5', 12)),
            ]:
            self.assertEqual(dist_naming.split_eggname(fn), nvb)

    def test_cleanup_reponame(self):
        for repo, a in [
            ('http://www.example.com/repo', '/'),
            ('https://www.example.com/repo/', ''),
            ('file:///home/repo', '/'),
            ('file:///home/repo/', ''),
            ('file://E:\\eggs', '\\'),
            ('file://E:\\eggs\\', ''),
            ('file://C:\\Desk and Top', '\\'),
            ]:
            self.assertEqual(dist_naming.cleanup_reponame(repo), repo + a)

        self.assertEqual(dist_naming.cleanup_reponame(sys.prefix),
                         'file://' + sys.prefix +
                         ('\\' if sys.platform == 'win32' else '/'))

    def test_comparable_spec1(self):
        cs = dist_naming.comparable_spec
        s1 = cs(dict(version='2008j', build=1))
        s2 = cs(dict(version='2008j', build=2))
        s3 = cs(dict(version='2009c', build=1))
        self.assert_(s1 < s2 < s3)

    def test_comparable_spec2(self):
        lst = []
        for v, b in [
            ('0.7.0', 1),
            ('0.8.0.dev4657', 2),
            ('0.8.0.dev5876', 1),
            ('0.8.0.dev19461', 3),
            ('0.8.0', 1),
            ]:
            lst.append(dist_naming.comparable_spec(dict(version=v, build=b)))

        for i in xrange(len(lst) - 1):
            self.assert_(lst[i] < lst[i + 1])


class TestReq(unittest.TestCase):

    def test_init(self):
        for req_string, name, version, build, strictness in [
            ('',          None,  None,  None, 0),
            (' \t',       None,  None,  None, 0),
            ('foo',       'foo', None,  None, 1),
            ('bar 1.9',   'bar', '1.9', None, 2),
            ('baz 1.8-2', 'baz', '1.8', 2,    3),
            ]:
            r = Req(req_string)
            self.assertEqual(r.name, name)
            self.assertEqual(r.version, version)
            self.assertEqual(r.build, build)
            self.assertEqual(r.strictness, strictness)

    def test_misc_methods(self):
        for req_string in ['', 'foo', 'bar 1.2', 'baz 2.6.7-5']:
            r = Req(req_string)
            self.assertEqual(str(r), req_string)
            self.assertEqual(r, r)
            self.assertEqual(eval(repr(r)), r)

        self.assertNotEqual(Req('foo'), Req('bar'))
        self.assertNotEqual(Req('foo 1.4'), Req('foo 1.4-5'))

    def test_matches(self):
        spec = dict(metadata_version='1.1', cname='foo_bar', version='2.4.1',
                    build=3, python=None)
        for req_string, m in [
            ('', True),
            ('foo', False),
            ('Foo-BAR', True),
            ('foo-Bar 2.4.1', True),
            ('FOO-Bar 1.8.7', False),
            ('FOO-BAR 2.4.1-3', True),
            ('FOO-Bar 2.4.1-1', False),
            ]:
            self.assertEqual(Req(req_string).matches(spec), m, req_string)

    def test_matches_py(self):
        spec = dict(metadata_version='1.1', cname='foo', version='2.4.1',
                    build=3, python=None)
        for py in ['2.4', '2.5', '2.6', '3.1']:
            requirement.PY_VER = py
            self.assertEqual(Req('foo').matches(spec), True)

        spec25 = dict(spec)
        spec25.update(dict(python='2.5'))

        spec26 = dict(spec)
        spec26.update(dict(python='2.6'))

        requirement.PY_VER = '2.5'
        self.assertEqual(Req('foo').matches(spec25), True)
        self.assertEqual(Req('foo').matches(spec26), False)

        requirement.PY_VER = '2.6'
        self.assertEqual(Req('foo').matches(spec25), False)
        self.assertEqual(Req('foo').matches(spec26), True)

    def test_dist_as_req(self):
        for req_string, s in [
            ('numpy', 1),
            ('numpy 1.3.0', 2),
            ('numpy 1.3.0-2', 3),
            ]:
            req = dist_as_req('file:///numpy-1.3.0-2.egg', s)
            self.assertEqual(req, Req(req_string))
            self.assertEqual(req.strictness, s)

    def test_add_Reqs_to_spec(self):
        spec = dict(name='dummy', packages=[])
        add_Reqs_to_spec(spec)
        self.assertEqual(spec['Reqs'], set())

        spec = dict(name='dumy', packages=['numpy 1.3.0'])
        add_Reqs_to_spec(spec)
        Reqs = spec['Reqs']
        self.assertEqual(len(Reqs), 1)
        self.assertEqual(Reqs, set([Req('numpy 1.3.0')]))



def eggs_rs(c, req_string):
    return [dist_naming.filename_dist(d)
            for d in c.install_sequence(Req(req_string))]


class TestChain0(unittest.TestCase):

    c = Chain(verbose=0)
    for fn in ['index-add.txt', 'index-5.1.txt', 'index-5.0.txt']:
        c.add_repo('file://%s/' % abspath(dirname(__file__)), fn)

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

    repos = {None: None}
    c = Chain(verbose=0)
    for name in 'epd', 'gpl':
        repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
        c.add_repo(repo, 'index-7.1.txt')
        repos[name] = repo

    def test_get_repo(self):
        for req_string, repo_name in [
            ('MySQL_python', 'gpl'),
            ('bitarray', 'epd'),
            ('foobar', None),
            ]:
            self.assertEqual(self.c.get_repo(Req(req_string)),
                             self.repos[repo_name])

    def test_get_dist(self):
        requirement.PY_VER = '2.7'
        for req_string, dist in [
            ('MySQL_python',  self.repos['gpl'] + 'MySQL_python-1.2.3-2.egg'),
            ('numpy',         self.repos['epd'] + 'numpy-1.6.0-3.egg'),
            ('swig',          self.repos['epd'] + 'swig-1.3.40-2.egg'),
            ('swig 1.3.36',   self.repos['epd'] + 'swig-1.3.36-3.egg'),
            ('swig 1.3.40-1', self.repos['epd'] + 'swig-1.3.40-1.egg'),
            ('swig 1.3.40-2', self.repos['epd'] + 'swig-1.3.40-2.egg'),
            ('foobar', None),
            ]:
            self.assertEqual(self.c.get_dist(Req(req_string)), dist)

    def test_reqs_dist(self):
        dist = self.repos['epd'] + 'FiPy-2.1-1.egg'
        self.assertEqual(self.c.reqs_dist(dist),
                         set([Req('distribute'),
                              Req('scipy'),
                              Req('numpy'),
                              Req('pysparse 1.2.dev203')]))

    def test_root(self):
        self.assertEqual(self.c.install_sequence(Req('numpy 1.5.1'),
                                                 mode='root'),
                         [self.repos['epd'] + 'numpy-1.5.1-2.egg'])

        self.assertEqual(self.c.install_sequence(Req('numpy 1.5.1-1'),
                                                 mode='root'),
                         [self.repos['epd'] + 'numpy-1.5.1-1.egg'])

    def test_order1(self):
        self.assertEqual(self.c.install_sequence(Req('numpy')),
                         [self.repos['epd'] + egg for egg in
                          'MKL-10.3-1.egg', 'numpy-1.6.0-3.egg'])

    def test_order2(self):
        self.assertEqual(self.c.install_sequence(Req('scipy')),
                         [self.repos['epd'] + egg for egg in
                          'MKL-10.3-1.egg', 'numpy-1.5.1-2.egg',
                          'scipy-0.9.0-1.egg'])


class TestChain2(unittest.TestCase):

    repos = {}
    c = Chain(verbose=0)
    for name in 'open', 'runner', 'epd':
        repo = 'file://%s/%s/' % (abspath(dirname(__file__)), name)
        c.add_repo(repo, 'index-7.1.txt')
        repos[name] = repo

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
        self.assert_(self.repos['epd'] + 'numpy-1.5.1-2.egg' in lst)


if __name__ == '__main__':
    unittest.main()
