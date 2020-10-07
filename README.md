# Format Blocks

Format Blocks is a Python library for building code formatters.

## Usage

Format Blocks provides a number of 'block' objects which know how to arrange text in various ways,
such as `LineBlock` which arranges elements on one line, and `StackBlock` which stacks them across
lines, and `WrapBlock` which wraps inserts line breaks at the margin.

However, the most import block is `ChoiceBlock`. ChoiceBlock accepts multiple formatting options,
and allows for the solver to pick the choices which _minimize the overall formatting cost_.

See the tests for some examples!

## Origins

Format Blocks is a fork of the guts of Google's R Formatter, [rfmt](https://github.com/google/rfmt).
Rfmt was structured as a formatting library with an R implementation, _almost_ entirely decoupled. To
create Format Blocks, I just did some final decoupling, then polished up the code and wrote some
extra features and tests.
