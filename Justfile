# Display help
default:
    @just --list

# Sync project dependencies
sync:
    uv sync

# Run linter and formatter
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Run tests
test:
    uv run pytest

# Run linting and tests (pre-commit check)
precommit: lint test

# Interactively setup credentials
setup:
    uv run sig-cloud-control setup

# Run the CLI application
run *args:
    uv run sig-cloud-control {{args}}
