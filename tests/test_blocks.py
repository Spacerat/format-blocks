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

# type: ignore

import pytest

from format_blocks import (
    BlockUsageError,
    ChoiceBlock,
    JoinedLineBlock,
    LineBlock,
    Options,
    StackBlock,
    TextBlock,
)

OPTS = Options()


@pytest.mark.parametrize("is_breaking", [True, False])
@pytest.mark.parametrize("text", ["", "foobar", "        "])
def test_text_block_basic(text, is_breaking):
    block = TextBlock(text, is_breaking=is_breaking)
    assert block.Render(OPTS) == text


def test_joined_line_block() -> None:
    block = JoinedLineBlock(
        [TextBlock("hello", is_breaking=True), TextBlock("world"), TextBlock("!")]
    )
    assert block.Render(OPTS) == "hello\nworld !"


def test_stack_block_basic():
    block = StackBlock([TextBlock("hello"), TextBlock("world"), TextBlock("!")])
    assert block.Render(OPTS) == "hello\nworld\n!"


@pytest.mark.parametrize(
    "options, expected",
    [
        (Options(margin_0=105, margin_1=125), "hello beautiful world !"),
        (Options(margin_1=10), "hello\nbeautiful\nworld\n!"),
    ],
)
def test_choice_block(options, expected):
    elements = [
        TextBlock("hello"),
        TextBlock("beautiful"),
        TextBlock("world"),
        TextBlock("!"),
    ]
    choices = [JoinedLineBlock(elements), StackBlock(elements)]
    block = ChoiceBlock(choices)

    assert block.Render(options) == expected


def test_composite_block_asserts_elements():
    with pytest.raises(BlockUsageError):
        LineBlock([])
