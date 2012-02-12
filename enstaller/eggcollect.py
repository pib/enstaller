import os
import json
import string
from os.path import isdir, isfile, join
from abc import ABCMeta, abstractmethod

import egginst

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


def info_from_metadir(meta_dir):
    path = join(meta_dir, '_info.json')
    if isfile(path):
        info = json.load(open(path))
        info['installed'] = True
        info['meta_dir'] = meta_dir
        return info
    return None


class EggCollection(AbstractEggCollection):

    def __init__(self, prefix, hook, evt_mgr=None):
        self.prefix = prefix
        self.hook = hook
        self.evt_mgr = evt_mgr
        self.verbose = False

        self.pkgs_dir = join(self.prefix, 'pkgs')

    def find(self, egg):
        n, v, b = split_eggname(egg)
        if self.hook:
            path = join(self.pkgs_dir,
                        '%s-%s-%d' % (n.lower(), v, b), 'EGG-INFO')
        else:
            path = join(self.prefix, 'EGG-INFO', n.lower())
        info = info_from_metadir(path)
        if info and info['key'] == egg:
            return info
        else:
            return None

    def query(self, **kwargs):
        name = kwargs.get('name')
        if self.hook:
            if not isdir(self.pkgs_dir):
                return
            for fn in sorted(os.listdir(self.pkgs_dir), key=string.lower):
                if name and not fn.startswith(name + '-'):
                    continue
                info = info_from_metadir(join(self.pkgs_dir, fn, 'EGG-INFO'))
                if info and all(info.get(k) == v
                                for k, v in kwargs.iteritems()):
                    yield info['key'], info
        else:
            egginfo_dir = join(self.prefix, 'EGG-INFO')
            if not isdir(egginfo_dir):
                return
            for fn in sorted(os.listdir(egginfo_dir), key=string.lower):
                if name and fn != name:
                    continue
                info = info_from_metadir(join(egginfo_dir, fn))
                if info and all(info.get(k) == v
                                for k, v in kwargs.iteritems()):
                    yield info['key'], info

    def install(self, egg, dir_path, extra_info=None):
        ei = egginst.EggInst(join(dir_path, egg),
                             prefix=self.prefix, hook=self.hook,
                             evt_mgr=self.evt_mgr,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.super_id = getattr(self, 'super_id', None)
        ei.install(extra_info)

    def remove(self, egg):
        assert self.find(egg), egg
        ei = egginst.EggInst(egg,
                             prefix=self.prefix, hook=self.hook,
                             evt_mgr=self.evt_mgr,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.super_id = getattr(self, 'super_id', None)
        ei.remove()


class JoinedEggCollection(AbstractEggCollection):

    def __init__(self, collections):
        self.collections = collections

    def find(self, egg):
        for collection in self.collections:
            info = collection.find(egg)
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
