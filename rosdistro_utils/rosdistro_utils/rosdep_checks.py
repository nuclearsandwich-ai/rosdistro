# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from contextlib import contextmanager
import os
import re

from rosdep2 import create_default_installer_context
from rosdep2.lookup import ResolutionError
from rosdep2.lookup import RosdepLookup
from rosdep2.rospkg_loader import DEFAULT_VIEW_KEY
from rosdep2.sources_list import update_sources_list
from rosdistro_utils.gitlines import guess_refs
from rosdistro_utils.yamlchanges import get_changed_yaml


@contextmanager
def _temporary_environment(**kwargs):
    orig = {
        k: os.environ.get(k) for k in kwargs.keys()
    }

    for k, v in kwargs.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)

    yield

    for k, v in orig.items():
        if v is not None:
            os.environ[k] = v
        else:
            os.environ.pop(k, None)


@contextmanager
def isolated_rosdep(rosdistro_path, stage_path):
    # Prepare sources list
    old_url = 'https://raw.githubusercontent.com/ros/rosdistro/master/'
    new_url = rosdistro_path.as_uri() + '/'
    sources_list_template = rosdistro_path / 'rosdep' / 'sources.list.d' / '20-default.list'
    sources_list_d = stage_path / 'sources.list.d'
    sources_list_d.mkdir(parents=True, exist_ok=True)
    with (sources_list_d / '20-default.list').open('w') as sources_list:
        with sources_list_template.open('r') as template:
            for line in template.readlines():
                sources_list.write(line.replace(old_url, new_url))

    # Prepare cache dir
    ros_home = stage_path / 'ros_home'
    ros_home.mkdir(parents=True, exist_ok=True)

    # Temporarily change environment variables
    env = {
        'ROS_HOME': str(ros_home),
        'ROSDISTRO_INDEX_URL': (rosdistro_path / 'index-v4.yaml').as_uri(),
    }

    with _temporary_environment(**env):
        # Update rosdep
        assert update_sources_list(
            sources_list_dir=str(sources_list_d),
            skip_eol_distros=True,
            quiet=False)

        yield


def get_changed_rosdeps(rosdistro_path):
    rosdep_files = rosdistro_path.glob('rosdep/*.yaml')
    if not rosdep_files:
        return

    refs = guess_refs(rosdistro_path)
    rosdep_changes = {}
    for rosdep_file in rosdep_files:
        changes = get_changed_yaml(rosdistro_path, rosdep_file, **refs)
        if changes:
            rosdep_changes[rosdep_file] = changes

    return rosdep_changes


def resolve_rosdep_changes(rosdistro_path, stage_path, platforms):
    changes = get_changed_rosdeps(rosdistro_path)
    if not changes:
        return

    with isolated_rosdep(rosdistro_path, stage_path):
        lookup = RosdepLookup.create_from_rospkg()
        view = lookup.get_rosdep_view(DEFAULT_VIEW_KEY)
        installer_context = create_default_installer_context()
        for path, rules_in_file in changes.items():
            for key, rules in rules_in_file.items():
                rosdep = view.lookup(key)
                for os_name, os_versions in platforms.items():
                    os_rules = rules.get(os_name, rules.get('*'))
                    if os_rules is None:
                        continue

                    os_installers = installer_context.get_os_installer_keys(os_name)
                    default_os_installer = installer_context.get_default_os_installer_key(os_name)

                    if isinstance(os_rules, dict):
                        if '*' in os_rules:
                            os_versions = {
                                v for v in os_rules.keys() if v != '*'
                            }.union(platforms[os_name])
                        elif any(set(os_rules.keys()).intersection(os_installers)):
                            os_versions = platforms[os_name]
                        else:
                            os_versions = set(os_rules.keys()).intersection(platforms[os_name])
                    else:
                        os_versions = platforms[os_name]

                    for os_version in os_versions:
                        installer, rule = rosdep.get_rule_for_platform(os_name, os_version, os_installers, default_os_installer)
                        if isinstance(rule, dict) and 'packages' in rule:
                            rule = rule['packages']
                        if not isinstance(rule, list):
                            continue
                        for package in rule:
                            yield (key, os_name, os_version, installer, package)
