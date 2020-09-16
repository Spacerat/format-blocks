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

""" A block language system for building language formatters. """

from itertools import chain
from typing import Iterable, List, Optional, Sequence

from . import support
from .base import LayoutBlock, Options, ParamDict
from .support import Solution


class BlockUsageError(Exception):
    pass


class TextBlock(LayoutBlock):
    """ A block containing a single unbroken string. """

    def __init__(self, text: str, is_breaking: bool = False):
        super().__init__(is_breaking)
        self.text = text

    def __repr__(self) -> str:
        return "*" * self.is_breaking + self.text

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        span = len(self.text)
        layout = support.Layout([support.LayoutElement.String(self.text)])
        # The costs associated with the layout of this block may require 1, 2 or 3
        # knots, depending on how the length of the text compares with the two
        # margins (m0 and m1) in options. Note that we assume
        # options.margin_1 >= options.margin_0 >= 0, as asserted in base.Options.Check().
        if span >= options.margin_1:
            s = support.Solution(
                [0],
                [span],
                [
                    (span - options.margin_0) * options.margin_0_cost
                    + (span - options.margin_1) * options.margin_1
                ],
                [options.margin_0_cost + options.margin_1_cost],
                [layout],
                options=options,
            )
        elif span >= options.margin_0:
            s = support.Solution(
                [0, options.margin_1 - span],
                [span] * 2,
                [
                    (span - options.margin_0) * options.margin_0_cost,
                    (options.margin_1 - options.margin_0) * options.margin_0_cost,
                ],
                [options.margin_0_cost, options.margin_0_cost + options.margin_1_cost],
                [layout] * 2,
                options=options,
            )
        else:
            s = support.Solution(
                [0, options.margin_0 - span, options.margin_1 - span],
                [span] * 3,
                [0, 0, (options.margin_1 - options.margin_0) * options.margin_0_cost],
                [
                    0,
                    options.margin_0_cost,
                    options.margin_0_cost + options.margin_1_cost,
                ],
                [layout] * 3,
                options=options,
            )
        return s.WithRestOfLine(rest_of_line)


class CompositeLayoutBlock(LayoutBlock):
    """The abstract superclass of blocks which contain other blocks (elements).

    Note that we assume at least one element.
    """

    def __init__(self, elements: Iterable[LayoutBlock]) -> None:
        super().__init__()
        self.elements: List[LayoutBlock] = list(elements)

        if not self.elements:
            raise BlockUsageError(
                "Composite Layout Blocks must contain at least one element."
            )

        for e in self.elements:
            if not isinstance(e, LayoutBlock):
                raise TypeError(f"{e} is not a LayoutBlock")

        self.is_breaking = (
            True if self.elements and self.elements[-1].is_breaking else False
        )

    def ReprLayoutBlocks(self) -> str:
        return "[%s]" % (", ".join(e.__repr__() for e in self.elements))

    def __repr__(self) -> str:
        return super().__repr__() + self.ReprLayoutBlocks()


class LineBlock(CompositeLayoutBlock):
    """ A block that places its elements in a single line. """

    def __init__(self, elements: Iterable[LayoutBlock]) -> None:
        super().__init__(elements)

    def extended(self, new_elements: Iterable[LayoutBlock]) -> "LineBlock":
        return self.__class__(chain(self.elements, new_elements))

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        if not self.elements:
            assert rest_of_line
            return rest_of_line

        element_lines: List[List[LayoutBlock]] = [[]]

        for i, elt in enumerate(self.elements):
            element_lines[-1].append(elt)
            if i < len(self.elements) - 1 and elt.is_breaking:
                element_lines.append([])

        if len(element_lines) > 1 and callable(options.break_element_lines):
            element_lines = options.break_element_lines(element_lines)

        line_solns = []
        for i, ln in enumerate(element_lines):
            ln_layout = None if i < len(element_lines) - 1 else rest_of_line
            for elt in ln[::-1]:
                ln_layout = elt.OptLayout(ln_layout, options)
            line_solns.append(ln_layout)
        soln = support.VSumSolution(list(filter(None, line_solns)), options)
        return soln.PlusConst(options.break_cost * (len(line_solns) - 1))


class ChoiceBlock(CompositeLayoutBlock):
    """ A block which contains alternate layouts of the same content. """

    # Note: All elements of a ChoiceBlock are breaking, if any are.
    def __init__(self, elements: Iterable[LayoutBlock]) -> None:
        super().__init__(elements)

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        # The optimum layout of this block is simply the piecewise minimum of its
        # elements' layouts.
        return support.MinSolution(
            [e.OptLayout(rest_of_line, options) for e in self.elements], options
        )


class MultBreakBlock(CompositeLayoutBlock):
    """ The abstract superclass of blocks that locally modify line break cost. """

    def __init__(self, elements: Iterable[LayoutBlock], break_mult: float = 1) -> None:
        super().__init__(elements)
        self.break_mult = break_mult

    def Parms(self) -> ParamDict:
        return {"break_mult": self.break_mult, **super().Parms()}


class StackBlock(MultBreakBlock):
    """ A block that arranges its elements vertically, separated by line breaks. """

    def __init__(self, elements: Iterable[LayoutBlock], break_mult: float = 1):
        super().__init__(elements, break_mult)

    def extended(self, new_elements: Iterable[LayoutBlock]) -> "StackBlock":
        return self.__class__(
            chain(self.elements, new_elements), break_mult=self.break_mult
        )

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        # The optimum layout for this block arranges the elements vertically. Only
        # the final element is composed with the continuation provided---all the
        # others see an empty continuation ("None"), since they face the end of
        # a line.
        if not self.elements:
            assert rest_of_line
            return rest_of_line
        soln = support.VSumSolution(
            [e.OptLayout(None, options) for e in self.elements[:-1]]
            + [self.elements[-1].OptLayout(rest_of_line, options)],
            options,
        )
        # Under some odd circumstances involving comments, we may have a degenerate
        # solution.
        if soln is None:
            return rest_of_line
        # Add the cost of the line breaks between the elements.
        return soln.PlusConst(
            options.break_cost * self.break_mult * max(len(self.elements) - 1, 0)
        )


class WrapBlock(MultBreakBlock):
    """ A block that arranges its elements like a justified paragraph. """

    def __init__(
        self,
        elements: Iterable[LayoutBlock],
        sep: str = " ",
        break_mult: float = 1,
        prefix: Optional[str] = None,
    ):
        super().__init__(elements)
        self.break_mult = break_mult
        self.sep = sep
        self.prefix = prefix
        self.elt_is_breaking = [e.is_breaking for e in elements]
        self.n = len(self.elements)

    def extended(self, new_elements: Iterable[LayoutBlock]) -> "WrapBlock":
        return self.__class__(
            chain(self.elements, new_elements),
            break_mult=self.break_mult,
            prefix=self.prefix,
        )

    def Parms(self) -> ParamDict:
        return {**super().Parms(), "sep": self.sep, "prefix": self.prefix}

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        # Computing the optimum layout for this class of block involves finding the
        # optimal packing of elements into lines, a problem which we address using
        # dynamic programming.
        sep_layout = TextBlock(self.sep).OptLayout(None, options)
        assert sep_layout is not None
        # TODO(pyelland): Investigate why OptLayout doesn't work here.
        prefix_layout = (
            TextBlock(self.prefix).DoOptLayout(None, options) if self.prefix else None
        )
        elt_layouts = [e.OptLayout(None, options) for e in self.elements]
        # Entry i in the list wrap_solutions contains the optimum layout for the
        # last n - i elements of the block.
        wrap_solutions: List[Optional[Solution]] = [None] * self.n
        # Note that we compute the entries for wrap_solutions in reverse order,
        # at each iteration considering all the elements from i ... n - 1 (the
        # actual number of elements considered increases by one on each iteration).
        # This means that the complete solution, with elements 0 ... n - 1 is
        # computed last.
        for i in range(self.n - 1, -1, -1):
            # To calculate wrap_solutions[i], consider breaking the last n - i
            # elements after element j, for j = i ... n - 1.
            # By induction, wrap_solutions contains the optimum layout of the
            # elements after the break, so the full layout is calculated by composing
            # a line with the elements before the break with the entry from
            # wrap_solutions corresponding to the elements after the break.
            # The optimum layout to be entered into wrap_solutions[i] is then simply
            # the minimum of the full layouts calculated for each j.
            solutions_i = []
            # The layout of the elements before the break is built up incrementally
            # in line_layout.
            if prefix_layout is None:
                line_layout = elt_layouts[i]
            else:
                line_layout = prefix_layout.WithRestOfLine(elt_layouts[i])

            last_breaking = self.elements[i].is_breaking
            for j in range(i, self.n - 1):
                solution_j = wrap_solutions[j + 1]
                assert solution_j
                full_soln = support.VSumSolution([line_layout, solution_j], options)
                # We adjust the cost of the full solution by adding the cost of the
                # line break we've introduced, and a small penalty
                # (options.late_pack_cost) to favor (ceteris paribus) layouts with
                # elements packed into earlier lines.
                solutions_i.append(
                    full_soln.PlusConst(
                        options.break_cost * self.break_mult
                        + options.late_pack_cost * (self.n - j)
                    )
                )
                # If the element at the end of the line mandates a following line break,
                # we're done.
                if last_breaking:
                    break
                # Otherwise, add a separator and the next element to the line layout
                # and continue.
                sep_elt_layout = sep_layout.WithRestOfLine(elt_layouts[j + 1])
                assert line_layout is not None
                line_layout = line_layout.WithRestOfLine(sep_elt_layout)
                last_breaking = self.elements[j + 1].is_breaking
            else:  # Not executed if last_breaking
                assert line_layout is not None
                solutions_i.append(line_layout.WithRestOfLine(rest_of_line))
            wrap_solutions[i] = support.MinSolution(solutions_i, options)
        # Once wrap_solutions is complete, the optimum layout for the entire block
        # is the optimum layout for the last n - 0 elements.
        result = wrap_solutions[0]
        assert result
        return result


class VerbBlock(LayoutBlock):
    """ A block that prints out several lines of text verbatim. """

    def __init__(
        self, lines: Sequence[str], is_breaking: bool = True, first_nl: bool = False
    ):
        super().__init__(is_breaking)
        self.lines = lines
        self.first_nl = first_nl

    def __repr__(self) -> str:
        return self.lines[0][:3] + "..." + self.lines[-1][-3:]

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        # The solution for this block is essentially that of a TextBlock(''), with
        # an abberant layout calculated as follows.
        l_elts = []
        for i, ln in enumerate(self.lines):
            if i > 0 or self.first_nl:
                l_elts.append(support.LayoutElement.NewLine())
            l_elts.append(support.LayoutElement.String(ln))
        layout = support.Layout(l_elts)
        span = 0
        sf = support.SolutionFactory()
        if options.margin_0 > 0:  # Prevent incoherent solutions
            sf.Append(0, span, 0, 0, layout)
        # options.margin_1 == 0 is absurd
        sf.Append(options.margin_0 - span, span, 0, options.margin_0_cost, layout)
        sf.Append(
            options.margin_1 - span,
            span,
            (options.margin_1 - options.margin_0) * options.margin_0_cost,
            options.margin_0_cost + options.margin_1_cost,
            layout,
        )
        return sf.MkSolution(options)
