# File: config.py
# Description: Core module for YACS
# Created: 2021/6/15 20:30
# Author: QiuJueqin (qiujueqin@gmail.com)


import os.path as op
import copy
from argparse import Namespace
from collections import OrderedDict
from contextlib import contextmanager

import yaml


class Config(OrderedDict):
    """
    Yet Another Configuration System: a plug-and-play configuration system
    with no 3rd-party dependency.
    You can instantiate a Config object from a yaml file:

        >>> cfg = Config('default_config.yaml')

    or from an existing dict:

        >>> dic = {'optimizer': 'adam', 'lr': 0.001}
        >>> cfg = Config(dic)

    or from a namespace created by argparse package:

        >>> import argparse
        >>> parser = argparse.ArgumentParser()
        >>> parser.add_argument('--batch_size', type=int, default=128)
        >>> cfg = Config(parser)

    or/and by merging from another Config object:

        >>> cfg = Config()
        >>> cfg.merge('another_config.yaml')

    Config supports two ways to access containing attributes:
    built-in dict way:

        >>> print(cfg['batch_size'])

    and dotted-dict way (more recommended since it requires less keyboard
    hits and save your line width):

        >>> print(cfg.batch_size)

    See README.md and examples/main.py for more usage hints.
    """

    def __init__(self, init=None):
        """
        :param init: dict | yaml filepath | namespace created by argparse
        """

        self.__dict__['__immutable__'] = False

        if init is None:
            super().__init__()
        elif isinstance(init, dict):
            self.from_dict(init)
        elif isinstance(init, str):
            self.from_yaml(init)
        elif isinstance(init, Namespace):
            self.from_namespace(init)
        else:
            raise TypeError(
                'can only instantiate from a dict, a yaml filepath, '
                'or an argparse.Namespace, but attempted to '
                'instantiate from a {}'.format(type(init))
            )

    # ---------------- Immutability ----------------

    @property
    def is_frozen(self):
        return self.__dict__['__immutable__']

    def freeze(self):
        self._set_immutable(True)

    @contextmanager
    def unfreeze(self):
        """
        When a Config is frozen (a default action once it is instantiated),
        you have to use the unfreeze() context manager to modify it.

        Example:
            >>> cfg = Config('default_config.yaml')
            >>> with cfg.unfreeze():
            >>>     cfg.batch_size = 512

        """
        try:
            self._set_immutable(False)
            yield self
        finally:
            self.freeze()

    def _set_immutable(self, is_immutable):
        """ Recursively set immutability """

        self.__dict__['__immutable__'] = is_immutable
        for v in self.values():
            if isinstance(v, Config):
                v._set_immutable(is_immutable)

    # ---------------- Set & Get ----------------

    def __setattr__(self, key, value):
        if self.is_frozen:
            raise AttributeError('attempted to modify an immutable Config')
        self[key] = value

    def __setitem__(self, key, value):
        if self.is_frozen:
            raise AttributeError('attempted to modify an immutable Config')
        super().__setitem__(key, value)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        else:
            raise AttributeError('attempted to access a non-existing attribute: {}'.format(key))

    # ---------------- Input ----------------

    def from_dict(self, dic):
        if not isinstance(dic, dict):
            raise TypeError('loaded from an invalid type: {}'.format(type(dic)))

        super().__init__(Config._from_dict(dic))
        self.freeze()

    def from_yaml(self, yaml_path):
        if not op.isfile(yaml_path):
            raise FileNotFoundError('could not find yaml file {}'.format(yaml_path))

        with open(yaml_path, 'r') as fp:
            dic = yaml.safe_load(fp)
        super().__init__(Config._from_dict(dic))
        self.freeze()

    def from_namespace(self, namespace):
        if not isinstance(namespace, Namespace):
            raise TypeError('loaded from an invalid type: {}'.format(type(namespace)))

        super().__init__(Config._from_dict(vars(namespace)))
        self.freeze()

    def merge(self, other, allow_new_attributes=False, keep_existed_attributes=True):
        """
        Recursively merge from other object

        :param other: Config object | dict | yaml filepath
        :param allow_new_attributes: whether allow to add new attributes

        Example:
            >>> cfg = Config({'optimizer': 'adam'})
            >>> other_cfg = Config({'lr': 0.001})
            >>> cfg.merge(other_cfg, allow_new_attributes=True)
            >>> cfg.print()
            optimizer: adam
            lr: 0.001

            >>> another_cfg = Config({'weight_decay': 1E-7})
            >>> cfg.merge(other_cfg, allow_new_attributes=False)
            AttributeError: attempted to add a new attribute: weight_decay

        :param keep_existed_attributes: whether keep those attributes
            that are not in 'other'. You may wish to trigger this if
            requires to completely replace a field (a filed refers to a
            collection of multiple attributes, i.e., a Config object in a
            Config object). See example/main.py: Example 5 for a practical
            usage.

        Example:
            >>> cfg1 = Config({'foo': {'Alice': 0, 'Bob': 1}})
            >>> cfg2 = cfg1.clone()
            >>> other_cfg = Config({'foo': {'Carol': 42}})
            >>> cfg1.merge(other_cfg, allow_new_attributes=True)
            >>> cfg1.print()
            foo:
                Alice: 0
                Bob: 1
                Carol: 42
            >>> cfg2.merge(other_cfg, allow_new_attributes=True, keep_existed_attributes=False)
            >>> cfg2.print()
            foo:
                Carol: 42
        """

        if isinstance(other, Config):
            new_config = other
        elif isinstance(other, (dict, str)):
            new_config = Config(other)
        else:
            raise TypeError('attempted to merge an unsupported object: {}'.format(type(other)))

        def _merge(source_config, other_config, allow_add_new, keep_existed):
            """ Recursively merge new config into source config """

            with source_config.unfreeze():
                for k, v in other_config.items():
                    if k not in source_config and not allow_add_new:
                        raise AttributeError('attempted to add a new attribute: {}'.format(k))

                    if isinstance(v, Config):
                        if k in source_config:
                            _merge(source_config[k], v, allow_add_new, keep_existed)
                        else:
                            source_config[k] = v
                    else:
                        source_config[k] = copy.deepcopy(v)

                if not keep_existed:
                    source_keys = list(source_config.keys())
                    for k in source_keys:
                        if k not in other_config and not isinstance(source_config[k], Config):
                            source_config.remove(k)

        _merge(self, new_config, allow_new_attributes, keep_existed_attributes)

    @classmethod
    def _from_dict(cls, dic):
        dic = copy.deepcopy(OrderedDict(dic))
        for k, v in dic.items():
            if isinstance(v, dict):
                dic[k] = cls(v)

        return dic

    # ---------------- Output ----------------

    def to_dict(self):
        """ Convert a Config object to a dict """
        def _to_dict(config):
            dic = dict(config)
            for k, v in dic.items():
                if isinstance(v, Config):
                    dic[k] = _to_dict(v)
            return dic

        return _to_dict(self)

    def dump(self, save_path):
        """ Dump a Config object to a yaml file """
        with open(save_path, 'w') as fp:
            yaml.safe_dump(self.to_dict(), fp)

    def clone(self):
        return Config(copy.deepcopy(self.to_dict()))

    # ---------------- Misc ----------------

    def remove(self, key):
        """ Remove an attribute """
        if self.is_frozen:
            raise AttributeError('attempted to modify an immutable Config')
        if key not in self:
            raise AttributeError('attempted to delete a non-existing attribute: {}'.format(key))

        del self[key]

    def __str__(self):
        texts = []
        for k, v in self.items():
            sep = '\n' if isinstance(v, Config) else ' '
            attr_str = '{}:{}{}'.format(str(k), sep, str(v))
            attr_str = self._indent(attr_str)
            texts.append(attr_str)

        return '\n'.join(texts)

    def __repr__(self):
        return '{} ({})'.format(self.__class__.__name__, super().__repr__())

    def print(self):
        print(self)

    @staticmethod
    def _indent(text, num_spaces=2):
        texts = text.split('\n')
        if len(texts) == 1:
            return texts[0]

        first = texts.pop(0)
        texts = [num_spaces * ' ' + line for line in texts]
        texts = '\n'.join(texts)
        return first + '\n' + texts
