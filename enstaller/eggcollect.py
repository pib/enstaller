import os
import json
from os.path import isdir, isfile, join
from abc import ABCMeta, abstractmethod

import egginst
from egginst.utils import pprint_fn_action, console_progress

from egg_meta import split_eggname


class AbstractEggCollection(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def find(self, egg):
        raise NotImplementedError

    @abstractmethod
    def query(self, **kwargs):
        raise NotImplementedError

    @abstractmethod
    def install(self, egg, dir_path):
        raise NotImplementedError

    @abstractmethod
    def remove(self, egg):
        raise NotImplementedError


def info_from_path(path):
    if isfile(path):
        info = json.load(open(path))
        info['installed'] = True
        return info
    return None


class EggCollection(AbstractEggCollection):

    def __init__(self, prefix, hook):
        self.prefix = prefix
        self.hook = hook

        self.verbose = False
        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.pkgs_dir = join(self.prefix, 'pkgs')

    def find(self, egg):
        n, v, b = split_eggname(egg)
        if self.hook:
            path = join(self.pkgs_dir, '%s-%s-%d' % (n.lower(), v, b),
                        'EGG-INFO', 'info.json')
            return info_from_path(path)
        else:
            info = self.find_name(n.lower())
            if info and info['key'] == egg:
                return info
            else:
                return None

    def find_name(self, name):
        if self.hook:
            index = dict(self.query(name=name))
            if len(index) == 1:
                return index.values()[0]
            else: # found none, or more then one
                return None
        else:
            assert name == name.lower()
            path = join(self.prefix, 'EGG-INFO', name, 'info.json')
            return info_from_path(path)
        

    def query(self, **kwargs):
        if self.hook:
            if not isdir(self.pkgs_dir):
                return
            for fn in os.listdir(self.pkgs_dir):
                path = join(self.pkgs_dir, fn, 'EGG-INFO', 'info.json')
                info = info_from_path(path)
                if info and all(info.get(k) == v
                                for k, v in kwargs.iteritems()):
                    yield info['key'], info
        else:
            egginfo_dir = join(self.prefix, 'EGG-INFO')
            if not isdir(egginfo_dir):
                return
            for fn in os.listdir(egginfo_dir):
                path = join(egginfo_dir, fn, 'info.json')
                info = info_from_path(path)
                if info and all(info.get(k) == v
                                for k, v in kwargs.iteritems()):
                    yield info['key'], info

    def install(self, egg, dir_path, extra_info=None):
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(join(dir_path, egg),
                             prefix=self.prefix, hook=self.hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install(extra_info)

    def remove(self, egg):
        self.action_callback(egg, 'removing')
        ei = egginst.EggInst(egg,
                             prefix=self.prefix, hook=self.hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.remove()


class JoinedEggCollection(AbstractEggCollection):

    def __init__(self, collections):
        self.collections = collections

    def where_from(self, egg):
        for collection in self.collections:
            if collection.find(egg):
                return collection
        return None

    def find(self, egg):
        for collection in self.collections:
            info = collection.find(egg)
            if info:
                return info
        return None

    def find_name(self, name):
        for collection in self.collections:
            info = collection.find_name(name)
            if info:
                return info
        return None

    def query(self, **kwargs):
        index = {}
        for collection in reversed(self.collections):
            index.update(collection.query(**kwargs))
        return index.iteritems()

    def install(self, egg, dir_path, extra_info=None):
        self.collections[0].install(egg, dir_path, extra_info)

    def remove(self, egg):
        self.collections[0].remove(egg)
