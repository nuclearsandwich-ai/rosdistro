# Copyright 2024 Open Source Robotics Foundation, Inc.
# Licensed under the Apache License, Version 2.0

import os
from pathlib import Path

from git import Repo
import unidiff


def _rangeify(sequence):
    chunk_last = None
    chunk_start = None

    for item in sequence:
        if chunk_last != item - 1:
            if chunk_start is not None:
                yield range(chunk_start, chunk_last + 1)
            chunk_start = item
        chunk_last = item

    if chunk_start is not None:
        yield range(chunk_start, chunk_last + 1)


def guess_refs(path):
    # TODO: More guessing - look at merge commits in CI, upstream tracking branches, etc
    refs = {}
    target_ref = os.environ.get('GITHUB_BASE_REF')
    if target_ref:
        refs['target_ref'] = target_ref
    head_ref = os.environ.get('GITHUB_HEAD_REF')
    if head_ref:
        refs['head_ref'] = head_ref
    return refs


def get_changed_lines(path, *, target_ref=None, head_ref=None, paths=None):
    repo = Repo(path)

    if head_ref is not None:
        head = repo.commit(head_ref)
    else:
        head = None

    if target_ref is not None:
        target = repo.commit(target_ref)
    elif head is not None:
        target = head.parents[0]
    else:
        target = repo.head.commit

    if head is not None:
        for base in repo.merge_base(target, head):
            break
        else:
            raise RuntimeError(
                f"No merge base found between '{target_ref}' and '{head_ref}'")
    else:
        base = target

    diffs = base.diff(head, paths, True)

    changed = {str(p.relative_to(path)): [] for p in paths}
    for diff in diffs:
        if not diff.b_path:
            continue
        patch = f"""--- {diff.a_path if diff.a_path else '/dev/null'}
+++ {diff.b_path}
{diff.diff.decode()}"""
        patchset = unidiff.PatchSet(patch)
        for file in patchset:
            for hunk in file:
                for line in hunk:
                    if line.line_type != unidiff.LINE_TYPE_ADDED:
                        continue
                    changed[file.path].append(line.target_line_no)

    for lines in changed.values():
        lines[:] = list(_rangeify(sorted(lines)))

    return changed
