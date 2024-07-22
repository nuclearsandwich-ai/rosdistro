from rosdistro_utils.review import Annotation
from rosdistro_utils.review import Criterion
from rosdistro_utils.review import Review


class ElementAnalyzer:

    @property
    def name(self) -> str:
        raise NotImplementedError()

    def abstain(self) -> bool:
        return False

    def review(self) -> tuple[list[Criterion], list[Annotation]]:
        raise NotImplementedError()


def build(analyzers):
    if any(analyzer.abstain() for analyzer in analyzers):
        return

    review = Review()
    for analyzer in analyzers:
        criteria, annotations = analyzer.review()

        if criteria:
            review.elements.setdefault(analyzer.name, [])
            review.elements[analyzer.name].extend(criteria)

        if annotations:
            review.annotations.extend(annotations)

    if not review.elements and not review.annotations:
        return

    return review
