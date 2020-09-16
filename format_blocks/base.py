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

""" Base functionality for the R formatter.

- Access to and manipulation of tool options.
"""

import io
import re
import sys
from dataclasses import dataclass
from typing import IO, Callable, Dict, List, Optional, Union

from .support import Console, Solution

ParamDict = Dict[str, Optional[Union[str, int, float, "LayoutBlock"]]]


@dataclass
class Options:
    margin_0: int = 0
    margin_0_cost: float = 0.05
    margin_1: int = 80
    margin_1_cost: float = 100
    break_cost: float = 2
    late_pack_cost: float = 1e-3
    break_element_lines: Optional[
        Callable[[List[List["LayoutBlock"]]], List[List["LayoutBlock"]]]
    ] = None

    def __post_init__(self) -> None:
        self.Check()

    def Check(self) -> None:
        """ Assertion verification for options. """
        try:
            assert self.margin_0 >= 0, "margin_0"
            assert self.margin_1 >= self.margin_0, "margin_1"
            assert self.margin_0_cost >= 0, "margin_0_cost"
            assert self.margin_1_cost >= 0, "margin_1_cost"
            assert self.break_cost >= 0, "break_cost"
            assert self.late_pack_cost >= 0, "late_pack_cost"
        except AssertionError as e:
            raise ValueError("Illegal option value for '%s'" % e.args[0])


class LayoutBlock:
    """ The abstract class at base of the block hierarchy. """

    def __init__(self, is_breaking: bool = False) -> None:
        # If a newline is mandated after this block.
        self.is_breaking = is_breaking

        # See OptLayout method below for use of layout_cache.
        self.layout_cache: Dict[Optional[Solution], Solution] = {}

    def Parms(self) -> ParamDict:
        """ A dictionary containing the parameters of this block. """
        return {}

    def ReprParms(self) -> str:
        """ The printed representation of this block's parameters. """
        if not self.Parms():
            return ""
        return "<%s>" % (
            ", ".join(
                "%s=%s" % (key, val.__repr__()) for key, val in self.Parms().items()
            )
        )

    def __repr__(self) -> str:
        return (
            re.sub("[a-z]", "", self.__class__.__name__ + "*" * self.is_breaking)
            + self.ReprParms()
        )

    def OptLayout(self, rest_of_line: Optional[Solution], options: Options) -> Solution:
        """Retrieve or compute the least-cost (optimum) layout for this block.

        Args:
          rest_of_line: a Solution object representing the text to the right of
            this block.
        Returns:
          A Solution object representing the optimal layout for this block and
          the rest of the line.
        """
        # Deeply-nested choice block may result in the same continuation supplied
        # repeatedly to the same block. Without memoisation, this may result in an
        # exponential blow-up in the layout algorithm.
        if rest_of_line not in self.layout_cache:
            self.layout_cache[rest_of_line] = self.DoOptLayout(rest_of_line, options)
        return self.layout_cache[rest_of_line]

    def DoOptLayout(
        self, rest_of_line: Optional[Solution], options: Options
    ) -> Solution:
        """Compute the least-cost (optimum) layout for this block.

        Args:
          rest_of_line: a Solution object representing the text to the right of
            this block.
        Returns:
          A Solution object representing the optimal layout for this block and
          the rest of the line.
        """
        # Abstract method.

    def PrintOn(self, options: Options, outp: IO[str]) -> None:
        """Print the contents of this block with the optimal layout.

        Args:
          outp: a stream on which output is to be printed.
        """
        soln = self.OptLayout(None, options)
        if soln:
            Console(outp, options.margin_0, options.margin_1).PrintLayout(
                soln.layouts[0]
            )

    def Print(self, options: Options) -> None:
        self.PrintOn(options, outp=sys.stdout)

    def Render(self, options: Options) -> str:
        stream = io.StringIO()
        self.PrintOn(options, outp=stream)
        return stream.getvalue()
