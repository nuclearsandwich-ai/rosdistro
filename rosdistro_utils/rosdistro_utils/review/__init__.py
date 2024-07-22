from collections import namedtuple
from enum import IntEnum
import itertools
import re
import textwrap


def _printed_len(text):
    return len(text) + sum(text.count(s) for s in RECOMMENDATION_SYMBOLS.values())


def _text_wrap(orig, width):
    match = re.match(r'^(\s*[-*] )', orig)
    subsequent_indent = ' ' * len(match.group(1) if match else '')
    return textwrap.wrap(
        orig, width=width, subsequent_indent=subsequent_indent,
    ) or ('',)


def _bubblify_text(text, width=78):
    result = '/' + ('—' * (width - 2)) + '\\' + ''

    if not isinstance(text, list):
        text = [text]

    text_width = width - 4
    for idx, segment in enumerate(text):
        if idx:
            result += '\n+' + ('-' * (width - 2)) + '+'
        for line in segment.splitlines():
            for chunk in _text_wrap(line, text_width):
                padding = ' ' * (text_width - _printed_len(chunk))
                result += '\n| ' + chunk + padding + ' |'

    result += '\n\\' + ('—' * (width - 2)) + '/'

    return result


def _format_code_block(file, lines, width, root=None):
    if root is None or not (root / file).is_file():
        if lines.start + 1 == lines.stop:
            return f'> In {file}, line {lines.start + 1}'
        else:
            return f'> In {file}, lines {lines.start + 1}-{lines.stop}'

    result = f'In {file}:'
    digits = len(str(lines.stop - 1))

    with (root / file).open() as f:
        for _ in range(1, lines.start):
            f.readline()
        for num, line in enumerate(f, start=lines.start):
            if num >= lines.stop:
                break
            result += f'\n  {num + 1:>{digits}} | {line[:width - digits - 5].rstrip()}'

    return result


class Recommendation(IntEnum):

    DISAPPROVE = 0
    NEUTRAL = 1
    APPROVE = 2


RECOMMENDATION_SYMBOLS = {
    Recommendation.DISAPPROVE: '\U0000274C',
    Recommendation.NEUTRAL: '\U0001F4DD',
    Recommendation.APPROVE: '\U00002705',
}


RECOMMENDATION_TEXT = {
    Recommendation.DISAPPROVE: 'Changes recommended',
    Recommendation.NEUTRAL: 'No changes recommended, but requires further review',
    Recommendation.APPROVE: 'No changes recommended',
}


Annotation = namedtuple('Annotation', ('file', 'lines', 'message'))


Criterion = namedtuple('Criterion', ('recommendation', 'rationale'))


class Review:

    def __init__(self):
        self._annotations = []
        self._elements = {}

    @property
    def annotations(self):
        return self._annotations

    @property
    def elements(self):
        return self._elements

    @property
    def recommendation(self):
        return min(
            (criterion.recommendation for criterion in itertools.chain.from_iterable(self.elements.values())),
            default=Recommendation.NEUTRAL)

    def summarize(self):
        if not self._elements:
            return '(No changes to supported elements were detected)'

        message = 'This is an automated review.'
        for element, criteria in self.elements.items():
            message += f'\n\nFor changes related to {element}:'
            for criterion in criteria:
                message += f"\n* {RECOMMENDATION_SYMBOLS[criterion.recommendation]} {textwrap.indent(criterion.rationale, '  ')[2:]}"

        return message

    def to_text(self, *, width=80, root=None):
        message = self.summarize()
        recommendation = self.recommendation

        result = textwrap.indent(
            f" {RECOMMENDATION_SYMBOLS[recommendation]} {RECOMMENDATION_TEXT[recommendation]}\n{_bubblify_text(message, width=width - 2)}",
            ' ')

        for annotation in self.annotations:
            result += '\n' + textwrap.indent(
                '\n' + _bubblify_text([
                    _format_code_block(annotation.file, annotation.lines, width=width - 9, root=root),
                    annotation.message,
                ], width=width - 5),
                '  ¦ ', predicate=lambda _: True)

        return result
