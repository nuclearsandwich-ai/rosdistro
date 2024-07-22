from pathlib import Path

from rosdistro_utils.review import Annotation
from rosdistro_utils.review import Criterion
from rosdistro_utils.review import Recommendation
from rosdistro_utils.review import Review

review = Review()

review.elements['rosdep'] = [
    Criterion(Recommendation.APPROVE, 'Contributor is awesome for opening a PR'),
    Criterion(Recommendation.APPROVE, 'Atmosphere is not currently on fire'),
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
