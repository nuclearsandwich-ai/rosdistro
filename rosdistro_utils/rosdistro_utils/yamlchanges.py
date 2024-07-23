# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from git import Repo
from rosdistro_utils.gitlines import get_changed_lines
from rosdistro_utils.yamllines import AnnotatedSafeLoader
import yaml


def _contains(needle, haystack):
    if needle is not None:
        for straw in haystack:
            if needle.start < straw.stop and needle.stop > straw.start:
                return True
    return False


def _isolate(data, changes):
    if not hasattr(data, '__lines__'):
        return

    if not _contains(data.__lines__, changes):
        data.__lines__ = None

    if isinstance(data, list):
        for item in data:
            if hasattr(item, '__lines__'):
                if _contains(item.__lines__, changes):
                    _isolate(item, changes)
                else:
                    item.__lines__ = None

    elif isinstance(data, dict):
        for k, v in tuple(data.items()):
            if hasattr(k, '__lines__'):
                if _contains(k.__lines__, changes):
                    # If key was modified, consider everything under it to
                    # have been modified as well
                    continue
                k.__lines__ = None

            _isolate(v, changes)


def get_changed_yaml(path, yaml_path, *, target_ref=None, head_ref=None):
    changes = get_changed_lines(path, target_ref=target_ref,
                                head_ref=head_ref, paths=(yaml_path,))

    for yaml_path, changes in changes.items():
        break

    repo = Repo(path)

    if head_ref is not None:
        data = yaml.load(
            repo.tree(head_ref)[yaml_path].data_stream,
            Loader=AnnotatedSafeLoader)
    else:
        with (path / yaml_path).open('r') as f:
            data = yaml.load(f, Loader=AnnotatedSafeLoader)

    _isolate(data, changes)

    return data


def prune_changed_yaml(data):
    if isinstance(data, list):
        for idx, item in reversed(tuple(enumerate(data))):
            if getattr(item, '__lines__', None):
                prune_changed_yaml(item)
                continue
            del data[idx]

    elif isinstance(data, dict):
        for k, v in tuple(data.items()):
            if getattr(k, '__lines__', None):
                continue
            if getattr(v, '__lines__', None):
                prune_changed_yaml(v)
                continue

            del data[k]
