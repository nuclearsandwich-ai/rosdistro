from pathlib import Path
from urllib.request import url2pathname
from urllib.parse import urlparse

from rosdistro import get_index

from rosdistro_utils.review import Annotation
from rosdistro_utils.review import Criterion
from rosdistro_utils.review import Recommendation
from rosdistro_utils.review.builder import ElementAnalyzer
from rosdistro_utils.yamlchanges import get_changed_yaml
from rosdistro_utils.yamlchanges import prune_changed_yaml


def _check_source_stanzas(criteria, annotations, distro_changes):
    return


class RosdistroAnalyzer(ElementAnalyzer):

    def __init__(self, rosdistro_path: Path, refs):
        self._rosdistro_path = rosdistro_path
        self._refs = refs

    @property
    def name(self) -> str:
        return 'rosdistro'

    def review(self) -> tuple[list[Criterion], list[Annotation]]:
        criteria = []
        annotations = []

        pkg_counts, distro_changes = self._get_distro_changes()
        if not distro_changes:
            # Bypass check if no rosdeps were changed
            return None, None

        _check_source_stanzas(criteria, annotations, distro_changes)

        return criteria, annotations

    def _get_distro_changes(self):
        index = get_index((self._rosdistro_path / 'index-v4.yaml').as_uri())
        rosdistro_files = {
            name: distro.get('distribution', []) for name, distro in index.distributions.items()
        }

        # rosdistro uses URLs, convert back to paths
        for rosdistro in rosdistro_files.keys():
            rosdistro_files[rosdistro] = [
                Path(url2pathname(urlparse(file).path))
                for file in rosdistro_files[rosdistro]
            ]

        rosdistro_changes = {}
        pkg_counts = {}
        for rosdistro, file_list in rosdistro_files.items():
            rosdistro_changes.setdefault(rosdistro, {})
            pkg_counts.setdefault(rosdistro, {})
            for rosdistro_file in file_list:
                changes = get_changed_yaml(self._rosdistro_path, rosdistro_file, **self._refs)
                if changes:
                    for key in changes.keys():
                        pkg_counts[rosdistro].setdefault(key, 0)
                        pkg_counts[rosdistro][key] += 1
                    prune_changed_yaml(changes)
                    if changes:
                        rosdep_changes[rosdistro][rosdep_file] = changes

        return pkg_counts, rosdistro_changes
