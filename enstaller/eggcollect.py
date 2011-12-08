import json
from os.path import isfile, join
from abc import ABCMeta, abstractmethod

import egginst
from egginst.utils import pprint_fn_action, console_progress

from egg_meta import split_eggname


class AbstractEggCollection(object):

    __metaclass__ = ABCMeta

    @abstractmethod
    def get_meta(self, egg):
        raise NotImplementedError

    @abstractmethod
    def install(self, egg, dir_path):
        raise NotImplementedError

    @abstractmethod
    def remove(self, egg):
        raise NotImplementedError


class EggCollection(AbstractEggCollection):

    def __init__(self, prefix, hook):
        self.prefix = prefix
        self.hook = hook

        self.verbose = False
        self.progress_callback = console_progress
        self.action_callback = pprint_fn_action

        self.pkgs_dir = join(self.prefix, 'pkgs')

    def get_meta(self, egg):
        n, v, b = split_eggname(egg)
        if self.hook:
            path = join(self.pkgs_dir, '%s-%s-%d' % (n.lower(), v, b),
                        'EGG-INFO', 'info.json')
            return self._info_from_path(path)
        else:
            info = self.get_meta_name(n.lower())
            if info and info['key'] == egg:
                return info
            else:
                return None

    def get_meta_name(self, name):
        assert not self.hook
        assert name == name.lower()
        path = join(self.prefix, 'EGG-INFO', name, 'info.json')
        return self._info_from_path(path)

    def _info_from_path(self, path):
        if isfile(path):
            info = json.load(open(path))
            info['installed'] = True
            return info
        return None

    def install(self, egg, dir_path):
        self.action_callback(egg, 'installing')
        ei = egginst.EggInst(join(dir_path, egg),
                             prefix=self.prefix, hook=self.hook,
                             pkgs_dir=self.pkgs_dir, verbose=self.verbose)
        ei.progress_callback = self.progress_callback
        ei.install()

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

    def get_meta(self, egg):
        for collection in self.collections:
            info = collection.get_meta(egg)
            if info:
                return info
        return None

    def get_meta_name(self, name):
        for collection in self.collections:
            info = collection.get_meta_name(name)
            if info:
                return info
        return None

    def install(self, egg, dir_path):
        self.collections[0].install(egg, dir_path)

    def remove(self, egg):
        self.collections[0].remove(egg)
