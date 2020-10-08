#!/usr/bin/env bash

set -euxo pipefail

poetry run autoflake --ignore-init-module-imports --remove-all-unused-imports -check --recursive .
poetry run isort --check .
poetry run black --check .
poetry run mypy format_blocks/