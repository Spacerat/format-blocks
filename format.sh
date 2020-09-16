#!/usr/bin/env bash

set -euxo pipefail

poetry run autoflake --ignore-init-module-imports --remove-all-unused-imports -ir .
poetry run isort .
poetry run black .
poetry run mypy format_blocks/