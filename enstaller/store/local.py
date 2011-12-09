# unused
import os
import json
from os.path import isfile, join

from base import AbstractStore


class LocalStore(AbstractStore):

    def __init__(self, location):
        self.root = location
        self._index_path = join(self.root, 'index.json')

    def connect(self, auth=None):
        pass

    def get(self, key):
        return self.get_data(key), self.get_metadata(key)

    def get_data(self, key):
        try:
            return open(self.path(key), 'rb')
        except IOError as e:
            raise KeyError(str(e))

    def get_metadata(self, key):
        self._read_index()
        return self._index[key]

    def set(self, key, value):
        self.set_data(key, value[0])
        self.set_metadata(key, value[1])

    def set_data(self, key, value, buffer_size=1048576):
        with open(self.path(key), 'wb') as fo:
            while True:
                chunk = value.read(buffer_size)
                if not chunk:
                    break
                fo.write(chunk)

    def set_metadata(self, key, value):
        self._read_index()
        self._index[key] = value
        self._write_index()

    def delete(self, key):
        os.unlink(self.path(key))
        self._read_index()
        del self._index[key]
        self._write_index()

    def _read_index(self):
        if isfile(self._index_path):
            self._index = json.load(open(self._index_path))
        else:
            self._index = {}

    def _write_index(self):
        with open(self._index_path, 'w') as f:
            json.dump(self._index, f, indent=2, sort_keys=True)

    def exists(self, key):
        self._read_index()
        return key in self._index

    def query(self, **kwargs):
        res = {}
        for key in self.query_keys(**kwargs):
            res[key] = self._index[key]
        return res

    def query_keys(self, **kwargs):
        self._read_index()
        for key, info in self._index.iteritems():
            if all(info.get(k) == v for k, v in kwargs.iteritems()):
                yield key

    def path(self, key):
        return join(self.root, key)
