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
precommit:
    @echo "Running pre-commit checks..."
    @uv run ruff check --fix . > /dev/null 2>&1 || (uv run ruff check --fix . && exit 1)
    @uv run ruff format . > /dev/null 2>&1 || (uv run ruff format . && exit 1)
    @uv run pytest > /dev/null 2>&1 || (uv run pytest && exit 1)
    @echo "✔︎  Pre-commit checks passed!"

# Interactively setup credentials
setup:
    uv run sig-cloud-control setup

# Run the CLI application
run *args:
    uv run sig-cloud-control {{args}}
