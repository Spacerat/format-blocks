#  Copyright 2015 Google Inc. All Rights Reserved.
#  Modifications: Copyright 2020 Joseph Atkins-Turkish
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

from itertools import chain
from typing import Container, Iterable, List, Optional, Union, cast

from typing_extensions import Protocol

from .base import LayoutBlock, Options, ParamDict
from .blocks import (
    ChoiceBlock,
    CompositeLayoutBlock,
    LineBlock,
    MultBreakBlock,
    StackBlock,
    TextBlock,
    WrapBlock,
)
from .support import Solution


def indented(content: LayoutBlock, indent: int = 2) -> LineBlock:
    """ Return the 'content' block prefixed with 'indent' spaces """
    return LineBlock([TextBlock(" " * indent), content])


def optionally_indented(
    prefix: Optional[LayoutBlock] = None,
    content: Optional[LayoutBlock] = None,
    suffix: Optional[LayoutBlock] = None,
    indent: int = 2,
) -> ChoiceBlock:
    """Place 'content' between 'prefix' and 'suffix', either:

    - On a new line, with a indent
    - All in one line, with no indent
    """
    content_block = content if content else TextBlock("")
    return ChoiceBlock(
        [
            StackBlock(
                filter(None, [prefix, indented(content_block, indent=indent), suffix])
            ),
            LineBlock(filter(None, [prefix, content, suffix])),
        ]
    )


class CompositeShotcutBlock(Protocol):
    @property
    def elements(self) -> List[LayoutBlock]:
        ...

    def CompositeOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        ...


class CompositeShortcutMixin:
    """ A Mixin for easing the implementation of blocks which contain a list of zero or more elements. """

    elements: List[LayoutBlock] = []

    def DoOptLayout(
        self: CompositeShotcutBlock, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        if not self.elements:
            return TextBlock("").OptLayout(rest_of_line, options)

        if len(self.elements) == 1:
            return self.elements[0].OptLayout(rest_of_line, options)

        return self.CompositeOptLayout(rest_of_line, options)


class JoinedLineBlock(CompositeShortcutMixin, CompositeLayoutBlock):
    """JoinedLineBlock joins a list of elements with a string,
    like [].join(str)
    """

    def __init__(
        self,
        elements: Iterable[LayoutBlock],
        joiner: Union[str, LayoutBlock] = " ",
        join_breaking: bool = False,
    ):
        super().__init__(elements)
        self.joiner = joiner
        self.join_breaking = join_breaking

    def extended(self, new_elements: Iterable[LayoutBlock]) -> "JoinedLineBlock":
        return self.__class__(chain(self.elements, new_elements), joiner=self.joiner)

    def Parms(self) -> ParamDict:
        return {
            **super().Parms(),
            "joiner": self.joiner,
            "join_breaking": self.join_breaking,
        }

    def CompositeOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        joiner = TextBlock(self.joiner) if isinstance(self.joiner, str) else self.joiner

        elements = [
            e for e in self.elements if not (isinstance(e, TextBlock) and e.text == "")
        ]

        joined: List[LayoutBlock] = []
        for element in self.elements[:-1]:
            joined.append(element)
            if not element.is_breaking or self.join_breaking:
                joined.append(joiner)

        joined.append(self.elements[-1])

        block = LineBlock(joined)
        return block.OptLayout(rest_of_line, options)


class _ConditionalJoinedLineBlock(CompositeShortcutMixin, CompositeLayoutBlock):
    """ TODO: document """

    def __init__(
        self,
        elements: Iterable[LayoutBlock],
        joiner: str = " ",
        no_space_left: Container[str] = frozenset({",", ".", ")"}),
        no_space_right: Container[str] = frozenset({".", "("}),
    ) -> None:
        super().__init__(elements)
        self.joiner = joiner
        self.no_space_left = no_space_left
        self.no_space_right = no_space_right

    def extended(
        self, new_elements: Iterable[LayoutBlock]
    ) -> "_ConditionalJoinedLineBlock":
        return self.__class__(
            chain(self.elements, new_elements),
            joiner=self.joiner,
            no_space_left=self.no_space_left,
            no_space_right=self.no_space_right,
        )

    def CompositeOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        result = [[self.elements[0]]]
        end = ""
        for element in self.elements[1:]:
            start = get_start_text(element)
            if (start in self.no_space_left) or (end in self.no_space_right):
                result[-1].append(element)
            else:
                result.append([element])
            end = get_end_text(element)

        return JoinedLineBlock(
            [LineBlock(x) for x in result], joiner=self.joiner
        ).OptLayout(rest_of_line, options)


class _JoinedStackBlock(CompositeShortcutMixin, MultBreakBlock):
    """ TODO: document """

    def __init__(
        self,
        elements: Iterable[LayoutBlock],
        joiner: LayoutBlock = TextBlock(","),
        break_mult: float = 1,
    ):
        super().__init__(elements, break_mult)
        self.joiner = joiner

    def extended(self, new_elements: Iterable[LayoutBlock]) -> "_JoinedStackBlock":
        return self.__class__(
            chain(self.elements, new_elements),
            break_mult=self.break_mult,
            joiner=self.joiner,
        )

    def CompositeOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        joiner = TextBlock(self.joiner) if isinstance(self.joiner, str) else self.joiner

        first: List[LayoutBlock] = [LineBlock([x, joiner]) for x in self.elements[:-1]]
        block = StackBlock(first + [self.elements[-1]], break_mult=self.break_mult)
        return block.OptLayout(rest_of_line, options)


class _WrapIfLongBlock(CompositeShortcutMixin, MultBreakBlock):
    """ TODO: document """

    def __init__(
        self,
        elements: Iterable[LayoutBlock],
        sep: str = " ",
        break_mult: float = 1,
        prefix: Optional[str] = None,
        wrap_len: int = 3,
    ):
        super().__init__(elements, break_mult=break_mult)
        self.prefix = prefix
        self.sep = sep
        self.wrap_len = wrap_len

    def extended(self, elements: Iterable[LayoutBlock]) -> "_WrapIfLongBlock":
        return self.__class__(
            chain(self.elements, elements),
            sep=self.sep,
            break_mult=self.break_mult,
            prefix=self.prefix,
            wrap_len=self.wrap_len,
        )

    def CompositeOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        if len(self.elements) >= self.wrap_len:
            block: LayoutBlock = WrapBlock(
                self.elements,
                sep=self.sep,
                break_mult=self.break_mult,
                prefix=self.prefix,
            )
        else:
            block = JoinedLineBlock(self.elements, joiner=TextBlock(self.sep))
        return block.OptLayout(rest_of_line, options)


def get_start(element: LayoutBlock) -> LayoutBlock:
    if isinstance(element, CompositeLayoutBlock):
        return get_start(element.elements[0])
    return element


def get_start_text(element: LayoutBlock) -> str:
    return cast(str, getattr(get_start(element), "text", ""))


def get_end(element: LayoutBlock) -> LayoutBlock:
    if isinstance(element, CompositeLayoutBlock):
        return get_start(element.elements[-1])
    return element


def get_end_text(element: LayoutBlock) -> str:
    return cast(str, getattr(get_end(element), "text", ""))
