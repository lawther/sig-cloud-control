# BEGIN SHARED RECIPES (DEFAULT) sha256:18670817947290ab
# Generated from agent_rules/snippets/default.just. Do not edit inside this block:
#      edit snippets/default.just, then run `just sync-justfile-recipes` in agent_rules.

# List available recipes
default:
    @just --list

# END SHARED RECIPES (DEFAULT)

# The shared recipes (synced from agent_rules) call this rather than spelling a runner.
uv_run := "uv run"

# Sync project dependencies
sync:
    uv sync
    @just setup-git-hooks

# Run linter and formatter
lint:
    uv run ruff format .
    uv run ruff check --fix .
    just extra-lints
    uv run ty check

# Check for bare dict/tuple return types and classes defined inside functions (ML001, ML002)
extra-lints:
    @uv run ml-lints src/

# Run tests
test:
    #!/usr/bin/env bash
    set -euo pipefail
    echo "Running tests..."
    cov_json=$(mktemp)
    trap 'rm -f "$cov_json"' EXIT
    uv run pytest --cov=sig_cloud_control --cov-branch --cov-report=json:"$cov_json"
    uv run python scripts/branch_summary.py "$cov_json"
    echo "Tests passed!"

# Setup the development environment from a fresh clone
setup-dev:
    @uv sync
    @just setup-git-hooks
    @echo "✅ Development environment setup complete!"

# Setup local git hooks
setup-git-hooks:
    @git config core.hooksPath .githooks
    @chmod +x .githooks/pre-commit
    @echo "✅ Git hooks set up!"

# Run linting and tests (pre-commit check)
# This Justfile is the Single Source Of Truth (SSOT) for all pre-commit checks.
# No additional linting or testing logic should be added anywhere else (e.g. CI configs).
precommit:
    #!/usr/bin/env bash
    if [[ "$(git config core.hooksPath 2>/dev/null)" != ".githooks" ]]; then
        echo "Git hooks not configured — installing now..."
        just setup-git-hooks
    fi
    echo "Running pre-commit checks..."
    uv lock --check || { echo "❌ uv.lock is out of sync with pyproject.toml"; exit 1; }
    tmpfile=$(mktemp)
    staged_list=$(mktemp)
    trap 'rm -f "$tmpfile" "$staged_list"' EXIT
    git diff --cached --name-only -z --diff-filter=d > "$staged_list"
    (
        set -e
        just _lint-justfile
        just lint
        xargs -r -0 git add < "$staged_list"
        just test
    ) > "$tmpfile" 2>&1
    status=$?
    if [ $status -ne 0 ]; then
        cat "$tmpfile"
        exit $status
    fi
    echo "✔︎  Pre-commit checks passed!"

# [private] Ensure Justfile recipes don't use && chains (which suppress set -e)
_lint-justfile:
    #!/usr/bin/env bash
    set -euo pipefail
    violations=$(awk '
        /^[[:space:]]+#!/ { in_shebang = 1 }
        /^[^[:space:]]/ && NF > 0 { in_shebang = 0 }
        !in_shebang && /&&/ && !/^[[:space:]]*#/ { print NR": "$0 }
    ' Justfile)
    if [[ -n "$violations" ]]; then
        echo "❌ Justfile recipes must not use && chains. Use separate lines for reliable error reporting."
        echo "$violations"
        exit 1
    fi

# Interactively setup credentials
setup:
    uv run sig-cloud-control setup

# Run the CLI application
run *args:
    uv run sig-cloud-control {{args}}

# BEGIN SHARED RECIPES (AI_READINESS) sha256:45e10abdfa181601
# Generated from agent_rules/snippets/ai_readiness.just. Do not edit inside this block:
#      edit snippets/ai_readiness.just, then run `just sync-justfile-recipes` in agent_rules.

# Analyse project source files to evaluate AI agent readiness
analyse-ai-readiness *args:
    @{{uv_run}} shared_scripts/analyse_ai_readiness.py {{args}}

# Check source file size thresholds for AI agent readiness (fails if threshold breached)
check-ai-readiness *args:
    @{{uv_run}} shared_scripts/analyse_ai_readiness.py --fail-on {{args}}

# END SHARED RECIPES (AI_READINESS)

# BEGIN SHARED RECIPES (CHECK_HOOKS_DRIFT) sha256:35dc21f648469e76
# Generated from agent_rules/snippets/check_hooks_drift.just. Do not edit inside this block:
#      edit snippets/check_hooks_drift.just, then run `just sync-justfile-recipes` in agent_rules.

# Verify .claude/hooks/ still matches agent_rules/hooks/. Requires the
# agent_rules repo as a sibling checkout; local/pre-commit only for now.
# Wiring this into CI needs agent_rules reachable there — see agent_rules-403.
check-hooks-drift:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x ../agent_rules/sync_hooks.py ]]; then
        echo "error: ../agent_rules/sync_hooks.py not found -- clone the agent_rules repo as a sibling" >&2
        exit 2
    fi
    if ! command -v uv >/dev/null; then
        echo "error: uv not found -- install uv; ../agent_rules/sync_hooks.py needs it to provision Python 3.13" >&2
        exit 2
    fi
    ../agent_rules/run_shared_script.py --check-failed-exit 3 -- ../agent_rules/sync_hooks.py check .

# END SHARED RECIPES (CHECK_HOOKS_DRIFT)
