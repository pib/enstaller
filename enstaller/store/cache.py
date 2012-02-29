# unused
import os
import json
from os.path import isfile, join, getmtime, getsize

from base import AbstractStore



class CacheStore(AbstractStore):

    def __init__(self, remote, local):
        self.remote = remote
        self.local = local

    def connect(self, auth=None):
        pass

    def _copy_if_necessary(self, key):
        if not self.local.exists(key):
            self.local.set(key, self.remote.get(key))

    def get(self, key):
        self._copy_if_necessary(key)
        return self.local.get(key)

    def get_data(self, key):
        self._copy_if_necessary(key)
        return self.local.get_data(key)

    def get_metadata(self, key):
        #self._copy_if_necessary(key)
        return self.remote.get_metadata(key)

    def exists(self, key):
        return self.remote.exists(key)

    def query(self, **kwargs):
        return self.remote.query(**kwargs)

    def query_keys(self, **kwargs):
        return self.remote.query_keys(**kwargs)
