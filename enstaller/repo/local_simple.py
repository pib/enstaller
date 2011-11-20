import os
import json
import hashlib
from glob import glob
from os.path import abspath, isfile, join, getmtime, getsize

from base import AbstractRepo

INDEX = 'index.json'


def md5_file(path):
    fi = open(path, 'rb')
    h = hashlib.new('md5')
    while True:
        chunk = fi.read(65536)
        if not chunk:
            break
        h.update(chunk)
    fi.close()
    return h.hexdigest()


def info_file(path):
    return dict(size=getsize(path),
                mtime=getmtime(path),
                md5=md5_file(path))


class LocalSimpleRepo(AbstractRepo):

    def __init__(self, location):
        self.root_dir = location

    def open(self, auth=None):
        pass

    def info(self):
        return {'summary': 'simple local filesystem repository'}

    def get(self, key, default=None):
        if self.exists(key):
            return open(self.path(key), 'rb')
        else:
            return default

    def set(self, key, value, buffer_size=1048576):
        with open(self.path(key), 'wb') as fo:
            while True:
                chunk = value.read(buffer_size)
                if not chunk:
                    break
                fo.write(chunk)

    def delete(self, key):
        os.unlink(self.path(key))

    def _read_index(self):
        if self.exists(INDEX):
            self._index = json.load(self.get(INDEX))
        else:
            self._index = None

    def get_metadata(self, key, default=None):
        path = self.path(key)
        if not isfile(path):
            return default
        info = {'size': getsize(path),
                'mtime': getmtime(path)}
        h = hashlib.new('md5')
        with open(path) as fi:
            while True:
                chunk = fi.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        info['md5'] = h.hexdigest()
        return info

    def exists(self, key):
        return isfile(self.path(join(key)))

    def query(self, **kwargs):
        res = {}
        for key in self.query_keys(**kwargs):
            if self._index is None:
                res[key] = self.get_metadata(key)
            else:
                res[key] = self._index[key]
        return res

    def _key_from_path(self, path):
        return abspath(path)[len(abspath(self.root_dir)) + 1:]

    def query_keys(self, **kwargs):
        self._read_index()
        if self._index is None:
            if kwargs:
                return
            else:
                for root, dirs, files in os.walk(self.root_dir):
                    for fn in files:
                        yield self._key_from_path(join(root, fn))
        else:
            for key, info in self._index.iteritems():
                if all(info.get(k) in (v, None)
                       for k, v in kwargs.iteritems()):
                    yield key

    def glob(self, pattern):
        for path in glob(join(self.root_dir, pattern)):
            key = self._key_from_path(path)
            if self.exists(key):
                yield key

    def path(self, key):
        return join(self.root_dir, key)


if __name__ == '__main__':
    r1 = LocalSimpleRepo('../../../repo')
    fn = 'bsdiff4-1.0.2-1.egg'
    print r1.exists(fn), r1.get_metadata(fn)
    r2 = LocalSimpleRepo('/Users/ischnell/repo2')
    r2.set(fn, r1.get(fn))
    for key in r1.query_keys():
        print '\t', key
    print r1.query()
    print list(r1.glob('*'))
