# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

from git import Head
from git import Repo
import pytest


@pytest.fixture(scope='session')
def git_repo(request, tmp_path_factory):
    repo_dir = tmp_path_factory.mktemp('git_repo')
    repo = Repo.init(repo_dir)
    request.addfinalizer(repo.close)

    repo.index.commit('Initial commit')

    base = repo.create_head('base')
    base.checkout()
    lines_txt = repo_dir / 'lines.txt'
    with open(lines_txt, 'w') as f:
        f.write('\n'.join(['a', 'b', 'c', 'd', 'e', 'B', 'E', '']))
    repo.index.add(lines_txt)
    repo.index.commit('Add lines.txt')

    repo.head.reference = Head(repo, 'refs/heads/orphan')
    repo.index.commit('Orphaned commit', parent_commits=None)

    repo.create_head('lines2', 'base').checkout()
    lines2_txt = repo_dir / 'lines2.txt'
    with open(lines2_txt, 'w') as f:
        f.write('\n'.join(['1', '2']))
    repo.index.add(lines2_txt)
    repo.index.remove(str(lines_txt), working_tree=True)
    repo.index.commit('Add lines2.txt, remove lines.txt')

    repo.create_head('less_c', 'base').checkout()
    with open(lines_txt, 'w') as f:
        f.write('\n'.join(['a', 'b', 'd', 'e', 'B', 'C', 'E', '']))
    repo.index.add(lines_txt)
    repo.index.commit("Remove 'c' from lines.txt")

    repo.create_head('less_c_d', 'less_c').checkout()
    with open(lines_txt, 'w') as f:
        f.write('\n'.join(['a', 'b', 'e', 'B', 'C', 'D', 'E', '']))
    repo.index.add(lines_txt)
    repo.index.commit("Remove 'd' from lines.txt")

    repo.create_head('less_a', 'base').checkout()
    with open(lines_txt, 'w') as f:
        f.write('\n'.join(['b', 'c', 'd', 'e', 'A', 'B', 'E', '']))
    repo.index.add(lines_txt)
    repo.index.commit("Remove 'a' from lines.txt")

    target = repo.create_head('merge_c_d_to_a', 'less_a').checkout()
    other = repo.heads['less_c_d']
    repo.index.merge_tree(other.commit)
    with open(lines_txt, 'w') as f:
        f.write('\n'.join(['b', 'e', 'A', 'B', 'C', 'D', 'E', '']))
    repo.index.add(lines_txt)
    repo.index.commit(
        "Merge branch 'less_c_d' into merge_c_d_to_a",
        parent_commits=(target.commit, other.commit))

    with open(lines_txt, 'a') as f:
        f.write('X\n')

    return repo
