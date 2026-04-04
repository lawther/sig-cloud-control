# Display help
default:
    @just --list

# Sync project dependencies
sync:
    uv sync
    @just install-hook

# Run linter and formatter
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Run tests
test:
    uv run pytest

# Install the git pre-commit hook
install-hook:
    @echo "#!/bin/sh" > .git/hooks/pre-commit
    @echo "just precommit" >> .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit
    @echo "✔︎  Git pre-commit hook installed!"

# Run linting and tests (pre-commit check)
# This Justfile is the Single Source Of Truth (SSOT) for all pre-commit checks.
# No additional linting or testing logic should be added anywhere else (e.g. CI configs).
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
