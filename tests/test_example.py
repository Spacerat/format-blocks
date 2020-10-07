from format_blocks import (
    ChoiceBlock,
    LayoutBlock,
    LineBlock,
    Options,
    StackBlock,
    TextBlock,
)


def format_list_of_lists(data, margin_0=10, margin_1=60):
    """
    Format 'data' - a list of lists/numbers/strings - with lines not exceeding 'margin_1'
    and a small penalty for exceeding margin_0.
    """

    return _format_list_of_lists(data).Render(
        Options(margin_0=margin_0, margin_1=margin_1)
    )


def _format_list_of_lists(data, current=LineBlock([TextBlock("")])) -> LayoutBlock:
    if isinstance(data, list):
        choices = [
            _format_block(data, "[]", current),
            _format_line(data, "[]", current),
        ]

        return ChoiceBlock(choices)

    else:
        return current.extended([TextBlock(repr(data))])


def _format_block(items, brackets, current) -> LayoutBlock:
    """ Format data in 'items' as an indented block with one item per line """

    stack = current.extended([TextBlock(brackets[0])])
    stack = StackBlock([stack])
    sub_blocks = [
        LineBlock([TextBlock("  "), _format_list_of_lists(x), TextBlock(", ")])
        for x in items
    ]
    stack = stack.extended(sub_blocks + [TextBlock(brackets[1])])

    return stack


def _format_line(items, brackets, current) -> LayoutBlock:
    """ Format data in 'items' on one unbroken line """

    current = current.extended([TextBlock(brackets[0])])

    for i, x in enumerate(items):
        if i == len(items) - 1:
            current = LineBlock([_format_list_of_lists(x, current)])
        else:
            current = LineBlock([_format_list_of_lists(x, current), TextBlock(", ")])

    current = current.extended([TextBlock(brackets[1])])

    return current


DATA = [
    123,
    456,
    789,
    123,
    [
        "a",
        [543, 5432, 5432, 432, 432, 432, 543, 432, 432, 432],
        "c",
        "d",
        [
            123,
            5432,
            765432,
            6543,
        ],
    ],
]

EXPECTED = """
[123, 456, 789, 123, [
  'a', 
  [543, 5432, 5432, 432, 432, 432, 543, 432, 432, 432], 
  'c', 
  'd', 
  [123, 5432, 765432, 6543], 
]]
"""


def test_example():
    """ Test a complex formatting example """

    assert format_list_of_lists(DATA).strip() == EXPECTED.strip()
