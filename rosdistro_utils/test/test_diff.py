# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

import pytest
from rosdistro_utils.gitlines import get_changed_lines


def test_diff(git_repo):
    # Check uncommitted
    lines = get_changed_lines(git_repo.working_dir)
    assert lines == {'lines.txt': [range(8, 9)]}

    # Check path targeting
    lines = get_changed_lines(git_repo.working_dir, paths=['lines.txt'])
    assert lines == {'lines.txt': [range(8, 9)]}

    # Check path targeting with no match
    lines = get_changed_lines(git_repo.working_dir, paths=['foo.txt'])
    assert lines == {}

    # Check explicit head
    lines = get_changed_lines(git_repo.working_dir, head_ref='less_a')
    assert lines == {'lines.txt': [range(5, 6)]}

    # Check explicit target with no head (including uncommitted)
    lines = get_changed_lines(git_repo.working_dir, target_ref='less_c')
    assert lines == {'lines.txt': [range(3, 4), range(6, 7), range(8, 9)]}

    # Check explicit head and target
    lines = get_changed_lines(git_repo.working_dir, target_ref='less_c',
                              head_ref='less_c_d')
    assert lines == {'lines.txt': [range(6, 7)]}

    # Check explicit head and target with multiple commits
    lines = get_changed_lines(git_repo.working_dir, target_ref='base',
                              head_ref='less_c_d')
    assert lines == {'lines.txt': [range(5, 7)]}

    # Check merge base behavior
    lines = get_changed_lines(git_repo.working_dir, target_ref='less_a',
                              head_ref='less_c_d')
    assert lines == {'lines.txt': [range(5, 7)]}

    # Check file being added
    lines = get_changed_lines(git_repo.working_dir, target_ref='base',
                              head_ref='lines2')
    assert lines == {'lines2.txt': [range(1, 3)]}

    # Check failure to find merge base
    with pytest.raises(RuntimeError):
        get_changed_lines(git_repo.working_dir, target_ref='orphan',
                          head_ref='less_a')
