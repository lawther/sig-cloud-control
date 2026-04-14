# Display help
default:
    @just --list

# Sync project dependencies
sync:
    uv sync
    @just setup-git-hooks

# Run linter and formatter
lint:
    uv run ruff check --fix .
    uv run ruff format .

# Run tests
test:
    uv run pytest

# Setup the development environment from a fresh clone
setup-dev:
    @uv sync
    @just setup-git-hooks
    @echo "✅ Development environment setup complete!"

# Setup local git hooks
setup-git-hooks:
    @echo "Setting up local git hooks..."
    @echo "#!/bin/sh" > .git/hooks/pre-commit
    @echo "# This hook invokes the Justfile, which is the Single Source Of Truth for precommit logic." >> .git/hooks/pre-commit
    @echo "# DO NOT add precommit logic here; add it to the 'precommit' recipe in the Justfile." >> .git/hooks/pre-commit
    @echo "just precommit" >> .git/hooks/pre-commit
    @chmod +x .git/hooks/pre-commit
    @echo "✅ Git hooks set up!"

# Run linting and tests (pre-commit check)
# This Justfile is the Single Source Of Truth (SSOT) for all pre-commit checks.
# No additional linting or testing logic should be added anywhere else (e.g. CI configs).
precommit:
    @echo "Running pre-commit checks..."
    @uv lock --check || { echo "❌ uv.lock is out of sync with pyproject.toml"; exit 1; }
    @tmpfile=$(mktemp); \
    trap 'rm -f "$$tmpfile"' EXIT; \
    if ! ( \
        grep -E "^[[:space:]]+#!.*" -A 10 Justfile | grep "&&" && { echo "❌ Shebang recipes must not use && chains. Use separate lines for reliable error reporting."; exit 1; } || true; \
        uv run ruff check --fix . && \
        uv run ruff format . && \
        uv run pytest \
    ) > "$$tmpfile" 2>&1; then \
        cat "$$tmpfile"; \
        exit 1; \
    fi
    @echo "✔︎  Pre-commit checks passed!"

# Interactively setup credentials
setup:
    uv run sig-cloud-control setup

# Run the CLI application
run *args:
    uv run sig-cloud-control {{args}}
