from abc import ABCMeta, abstractmethod


class AbstractStore(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def connect(self, authentication=None):
        raise NotImplementedError

    def info(self):
        raise NotImplementedError

    @abstractmethod
    def get(self, key):
        raise NotImplementedError

    def set(self, key, value, buffer_size=1048576):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

    @abstractmethod
    def get_data(self, key):
        raise NotImplementedError

    @abstractmethod
    def get_metadata(self, key, select=None):
        raise NotImplementedError

    def set_data(self, key, data):
        raise NotImplementedError

    def set_metadata(self, key, metadata):
        raise NotImplementedError

    def update_metadata(self, key, metadata):
        raise NotImplementedError

    @abstractmethod
    def exists(self, key):
        raise NotImplementedError

    @abstractmethod
    def query(self, select=None, **kwargs):
        raise NotImplementedError


    def query_keys(self, **kwargs):
        return self.query(**kwargs).keys()
