# Copyright (c) 2024, Open Source Robotics Foundation
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#     * Redistributions of source code must retain the above copyright
#       notice, this list of conditions and the following disclaimer.
#     * Redistributions in binary form must reproduce the above copyright
#       notice, this list of conditions and the following disclaimer in the
#       documentation and/or other materials provided with the distribution.
#     * Neither the name of the Willow Garage, Inc. nor the names of its
#       contributors may be used to endorse or promote products derived from
#       this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

import os
import tarfile

from . import open_compressed_url
from . import PackageEntry
from . import RepositoryCacheCollection
import ucl
import yaml


class SplitCollectionLoader(yaml.BaseLoader):

    def compose_document(self):
        if self.check_event(yaml.DocumentStartEvent):
            self.get_event()
            if self.check_event(yaml.CollectionStartEvent):
                self.get_event()

        node = self.compose_node(None, None)

        if self.check_event(yaml.CollectionEndEvent):
            self.get_event()
        if self.check_event(yaml.DocumentEndEvent):
            self.get_event()
            self.anchors = {}

        return node


class SubdivisionLoader(yaml.BaseLoader):

    class _SubdivisionFound(BaseException):
        pass

    def is_subdivision(self, parent, index):
        raise NotImplementedError()

    def parse_implicit_document_start(self):
        event = super().parse_implicit_document_start()
        if self.state is not self.search_for_subdivision:
            self.states.append(self.state)
            self.state = self.search_for_subdivision
        return event

    def parse_document_start(self):
        event = super().parse_document_start()
        self.states.append(self.state)
        self.state = self.search_for_subdivision
        return event

    def search_for_subdivision(self):
        self.state = self.states.pop()

        self.compose_node = self.search_for_node
        try:
            self.compose_node(None, None)
        except self._SubdivisionFound:
            pass
        else:
            token = self.peek_token()
            return self.process_empty_scalar(token.end_mark)
        finally:
            del self.compose_node

        self.states.append(self.discard_until_document_end)
        self.check_event()
        return self.current_event

    def discard_until_document_end(self):
        self.state = self.states.pop()
        event = self.state()
        while not isinstance(event, (yaml.DocumentEndEvent, yaml.StreamEndEvent)):
            event = self.state()
        return event

    def search_for_node(self, parent, index):
        if self.is_subdivision(parent, index):
            raise self._SubdivisionFound()
        return super().compose_node(parent, index)


class PackagesOnlyLoader(
    SplitCollectionLoader,
    SubdivisionLoader,
    yaml.SafeLoader,
):

    def is_subdivision(self, parent, index):
        return (
            isinstance(parent, yaml.MappingNode) and
            isinstance(index, yaml.ScalarNode) and
            index.value == 'packages' and
            self.check_event(yaml.SequenceStartEvent)
        )


def _enumerate_packages_values(data_file):
    for val in yaml.load_all(data_file, Loader=PackagesOnlyLoader):
        yield val


def _enumerate_data_entries(resolved_url, data_name):
    data_url = os.path.join(resolved_url, f'{data_name}.pkg')
    with open_compressed_url(data_url, compression='lzma') as f:
        with tarfile.open(mode='r|', fileobj=f) as tf:
            for ti in tf:
                if ti.name != data_name:
                    continue
                with tf.extractfile(ti) as df:
                    yield from _enumerate_packages_values(df)
                break
            else:
                raise FileNotFoundError(data_name)


def enumerate_pkg_packages(root_url, os_name, os_code_name, os_arch):
    """
    Enumerate packages in an PKG repository.

    :param root_url: the PKG repository root URL.
    :param os_name: the name of the OS associated with the repository.
    :param os_code_name: the OS version associated with the repository.
    :param os_arch: the system architecture associated with the repository.

    :returns: an enumeration of package entries.
    """
    abi_os_name = {
        'freebsd': 'FreeBSD',
    }.get(os_name, os_name)
    abi = f'{abi_os_name}:{os_code_name}:{os_arch}'
    resolved_url = root_url.replace('${ABI}', abi)
    meta_url = os.path.join(resolved_url, 'meta.conf')

    with open_compressed_url(meta_url) as f:
        meta = ucl.load(f.read().decode())

    for pkg in _enumerate_data_entries(resolved_url, meta['data']):
        if pkg is not None:
            url = os.path.join(resolved_url, pkg['path'])
            yield PackageEntry(pkg['name'], pkg['version'], url, pkg['origin'])


def pkg_root_url(root_url):
    """
    Create an enumerable cache for a PKG repository.

    :param base_url: the URL of the PKG repository root.

    :returns: an enumerable repository cache instance.
    """
    return RepositoryCacheCollection(
        lambda os_name, os_code_name, os_arch:
            enumerate_pkg_packages(root_url, os_name, os_code_name, os_arch))
