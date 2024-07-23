from pathlib import Path

from rosdep2 import create_default_installer_context

from rosdistro_utils.review import Annotation
from rosdistro_utils.review import Criterion
from rosdistro_utils.review import Recommendation
from rosdistro_utils.review.builder import ElementAnalyzer
from rosdistro_utils.yamlchanges import get_changed_yaml
from rosdistro_utils.yamlchanges import prune_changed_yaml


EOL_PLATFORMS = {
    'debian': {
        'lenny',
        'squeeze',
        'wheezy',
        'jessie',
        'stretch',
        'buster',
    },
    'fedora': {
        str(n) for n in range(21, 39)
    },
    'rhel': {
        str(n) for n in range(3, 8)
    },
    'ubuntu': {
        'trusty',
        'utopic',
        'vivid',
        'wily',
        'xenial',
        'yakkety',
        'zesty',
        'artful',
        'bionic',
        'cosmic',
        'disco',
        'eoan',
        'groovy',
        'hirsute',
        'impish',
        'kinetic',
        'lunar',
        'mantic',
    },
}


def _check_key_names(criteria, annotations, changed_rosdeps, key_counts):
    # Bypass check if no new keys were added
    if not any(
        getattr(key, '__lines__', None)
        for changes in changed_rosdeps.values()
        for key in changes.keys()
    ):
        return

    recommendation = Recommendation.APPROVE
    problems = set()

    # Pip-only rules should end in -pip
    for file, changes in changed_rosdeps.items():
        if file.name != 'python.yaml':
            continue
        for k, v in changes.items():
            if not getattr(k, '__lines__', None):
                continue

            pip_only = all(
                isinstance(rule, dict) and set(rule.keys()) == {'pip'}
                for rule in v.values())
            if pip_only != k.endswith('-pip'):
                recommendation = Recommendation.DISAPPROVE
                problems.add(
                    "Keys which contain only pip rules should end in '-pip'")
                annotations.append(Annotation(
                    'rosdep/python.yaml',
                    k.__lines__,
                    f"This key should{'' if pip_only else ' not'} end in '-pip'"))

    # Python keys should go in python.yaml
    for file, changes in changed_rosdeps.items():
        if file.name == 'python.yaml':
            continue
        for key in changes.keys():
            if not getattr(key, '__lines__', None):
                continue

            if key.startswith('python'):
                recommendation = Recommendation.DISAPPROVE
                problems.add(
                    "Keys for Python packages should go in 'python.yaml'")
                annotations.append(Annotation(
                    file, key.__lines__, 'This key belongs in python.yaml'))

    # Key names SHOULD match the ubuntu apt package name
    for file, changes in changed_rosdeps.items():
        for key, rules in changes.items():
            if not getattr(key, '__lines__', None):
                continue
            ubuntu_rule = rules.get('ubuntu', {})
            if isinstance(ubuntu_rule, dict) and '*' in ubuntu_rule:
                ubuntu_rule = ubuntu_rule['*']
            if isinstance(ubuntu_rule, dict):
                if 'apt' not in ubuntu_rule:
                    continue
                ubuntu_rule = ubuntu_rule['apt']
                if isinstance(ubuntu_rule, dict) and 'packages' in ubuntu_rule:
                    ubuntu_rule = ubuntu_rule['packages']
            if not ubuntu_rule:
                continue
            if key not in ubuntu_rule:
                recommendation = min(recommendation, Recommendation.NEUTRAL)
                problems.add('New key names should typically match the Ubuntu package name')
                annotations.append(Annotation(
                    file, key.__lines__, 'This key does not match the Ubuntu package name'))

    # Keys should not be defined in multiple places
    for file, changes in changed_rosdeps.items():
        for key in changes.keys():
            if not getattr(key, '__lines__', None):
                continue
            if key_counts.get(key, 0) > 1:
                recommendation = Recommendation.DISAPPROVE
                problems.add(
                    'Keys names should be unique across the entire database')
                annotations.append(Annotation(
                    file, key.__lines__, 'This key is also defined elsewhere'))

    if problems:
        message = 'There are problems with the names of new rosdep keys:\n- ' + '\n- '.join(problems)
    else:
        message = 'New rosdep keys are named appropriately'

    criteria.append(Criterion(recommendation, message))


def _check_platforms(criteria, annotations, changed_rosdeps):
    # Bypass check if no platforms were added
    if not any(
        os != '*' and (getattr(os, '__lines__', None) or (
            isinstance(rule, dict) and any(
                getattr(release, '__lines__', None) and release != '*'
                for release in rule.keys()
            )
        ))
        for changes in changed_rosdeps.values()
        for rules in changes.values()
        for os, rule in rules.items()
    ):
        return

    recommendation = Recommendation.APPROVE
    problems = set()

    installer_context = create_default_installer_context()
    os_keys = {'*'}.union(installer_context.get_os_keys())

    # New explicit rules for EOL platforms are not allowed
    # New rules for unsupported OSs are not allowed
    for file, changes in changed_rosdeps.items():
        for rules in changes.values():
            for os, rule in rules.items():
                if os not in os_keys and getattr(os, '__lines__', None):
                    recommendation = Recommendation.DISAPPROVE
                    problems.add(
                        'One or more explicitly provided platforms are not supported by rosdep')
                    annotations.append(Annotation(
                        file, os.__lines__,
                        f'This OS is not supported by rosdep'))
                elif isinstance(rule, dict):
                    eol_releases = EOL_PLATFORMS.get(os, set())
                    for release in rule.keys():
                        if release not in eol_releases or not getattr(release, '__lines__', None):
                            continue
                        recommendation = Recommendation.DISAPPROVE
                        problems.add(
                            'One or more explicitly provided platforms are no longer supported')
                        annotations.append(Annotation(
                            file, release.__lines__,
                            f'This release is no longer a supported version of {os}'))

    if problems:
        message = 'There are problems with explicitly provided platforms:\n- ' + '\n- '.join(problems)
    else:
        message = 'Platforms for new rosdep rules are valid'

    criteria.append(Criterion(recommendation, message))


def _check_installers(criteria, annotations, changed_rosdeps):
    # Bypass check if no explicit installers were added
    if not any(
        os != '*' and isinstance(rule, dict) and any(
            isinstance(sub_rule, dict) and any(
                getattr(installer, '__lines__', None)
                for installer in sub_rule.keys()
            )
            for sub_rule in rule.values()
        )
        for changes in changed_rosdeps.values()
        for rules in changes.values()
        for os, rule in rules.items()
    ):
        print(f'{changed_rosdeps}')
        return

    recommendation = Recommendation.APPROVE
    problems = set()

    installer_context = create_default_installer_context()

    for file, changes in changed_rosdeps.items():
        for rules in changes.values():
            for os, rule in rules.items():
                if os == '*' or not isinstance(rule, dict):
                    continue
                try:
                    os_installers = installer_context.get_os_installer_keys(os)
                except KeyError:
                    continue
                for sub_rule in rule.values():
                    if not isinstance(sub_rule, dict):
                        continue
                    for installer in sub_rule.keys():
                        if not getattr(installer, '__lines__', None):
                            continue
                        if installer in os_installers:
                            continue
                        recommendation = Recommendation.DISAPPROVE
                        problems.add(
                            'One or more explicitly provided installer is not supported by rosdep')
                        annotations.append(Annotation(
                            file, installer.__lines__,
                            f'This installer is not supported for {os}'))

    if problems:
        message = 'There are problems with explicitly provided installers:\n- ' + '\n- '.join(problems)
    else:
        message = 'Installers for new rosdep rules are valid'

    criteria.append(Criterion(recommendation, message))


class RosdepAnalyzer(ElementAnalyzer):

    def __init__(self, rosdistro_path: Path, refs):
        self._rosdistro_path = rosdistro_path
        self._refs = refs

    @property
    def name(self) -> str:
        return 'rosdep'

    def review(self) -> tuple[list[Criterion], list[Annotation]]:
        criteria = []
        annotations = []

        key_counts, changed_rosdeps = self._get_changed_rosdeps()
        if not changed_rosdeps:
            # Bypass check if no rosdeps were changed
            return None, None

        _check_key_names(criteria, annotations, changed_rosdeps, key_counts)
        _check_platforms(criteria, annotations, changed_rosdeps)
        _check_installers(criteria, annotations, changed_rosdeps)

        fixed_annotations = []
        for annotation in annotations:
            if isinstance(annotation.file, Path):
                fixed_annotations.append(Annotation(
                    str(annotation.file.relative_to(self._rosdistro_path)),
                    annotation.lines, annotation.message))
            else:
                fixed_annotations.append(annotation)

        return criteria, fixed_annotations

    def _get_changed_rosdeps(self):
        rosdep_files = self._rosdistro_path.glob('rosdep/*.yaml')
        if not rosdep_files:
            return None, None

        rosdep_changes = {}
        key_counts = {}
        for rosdep_file in rosdep_files:
            changes = get_changed_yaml(self._rosdistro_path, rosdep_file, **self._refs)
            if changes:
                for key in changes.keys():
                    key_counts.setdefault(key, 0)
                    key_counts[key] += 1
                prune_changed_yaml(changes)
                if changes:
                    rosdep_changes[rosdep_file] = changes

        return key_counts, rosdep_changes
