import os
from pathlib import Path

from rosdistro_utils.gitlines import guess_refs
from rosdistro_utils.review.builder import build
from rosdistro_utils.review.github import post_review
from rosdistro_utils.rosdep_analyzer import RosdepAnalyzer
from rosdistro_utils.rosdistro_analyzer import RosdistroAnalyzer

rosdistro_path = Path.cwd()

refs = guess_refs(rosdistro_path)

analyzers = (
    RosdepAnalyzer(rosdistro_path, refs),
    RosdistroAnalyzer(rosdistro_path, refs),
)

review = build(analyzers)
if review:
    print(review.to_text(root=rosdistro_path))

    if len(sys.argv) > 1 and 'GITHUB_TOKEN' in os.environ and 'GITHUB_REPOSITORY' in os.environ:
        post_review(os.environ['GITHUB_REPOSITORY'], int(sys.argv[1]), review)
