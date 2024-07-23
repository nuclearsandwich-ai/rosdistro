import os
from pathlib import Path

from github import Auth
from github import Github
from github.PullRequest import ReviewComment

from rosdistro_utils.review import Annotation
from rosdistro_utils.review import Criterion
from rosdistro_utils.review import Recommendation
from rosdistro_utils.review import Review


RECOMMENDATION_EVENTS = {
    Recommendation.DISAPPROVE: 'REQUEST_CHANGES',
    Recommendation.NEUTRAL: 'COMMENT',
    Recommendation.APPROVE: 'APPROVE',
}


def post_review(repo, pr_id, review):
    comments = [
        ReviewComment(path=a.file, body=a.message, line=a.lines.stop, side='RIGHT', start_line=a.lines.start, start_side='RIGHT')
        for a in review.annotations
    ]

    a = Auth.Token(os.environ.get('GITHUB_TOKEN'))
    g = Github(auth=a)
    r = g.get_repo(repo)
    pr = r.get_pull(pr_id)

    message = review.summarize()
    recommendation = review.recommendation

    pr.create_review(body=message, event=RECOMMENDATION_EVENTS[recommendation], comments=comments)


if __name__ == '__main__':
    review = Review()

    review.elements['rosdep'] = [
        Criterion(Recommendation.APPROVE, 'No EOL rules were added'),
        Criterion(Recommendation.NEUTRAL, 'Not all rules could be verified programmatically'),
        Criterion(Recommendation.DISAPPROVE, "Rules exclusively for pip packages should have the '-pip' suffix and should be placed in 'python.yaml'"),
    ]

    review.annotations.append(Annotation(
        'rosdep/python.yaml', range(31, 35), """Keys which contain only pip rules should have the '-pip' suffix.

```suggestion
aioraven-pip:
  '*':
    pip:
      packages: [aioraven]
```
"""))

    print('\n' + review.to_text(root=Path('/home/cottsay/rosdistro')) + '\n')

    post_review('cottsay/rosdistro', 5, review)
