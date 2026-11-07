# BEGIN FLEET RECIPES (CORE)
# Generated from agent_rules payload/core/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# List available recipes
default:
    @just --list

# Fail if a file, block or hook registration the fleet manages here has changed since sync
# wrote it. Reads only this repo, so it runs the same in the git hook and in CI.
check-fleet:
    @uv run --script .fleet/core/check_integrity.py

# Every check the fleet requires of this repo. This repo's own precommit depends on it, so a
# check added here reaches every repo's gate with the next sync.
precommit-fleet: check-fleet

# Land this repo's open Dependabot PRs on main, one tested commit per PR. Never pushes.
apply-dependabot *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x ../agent_rules/apply_dependabot.py ]]; then
        echo "error: ../agent_rules/apply_dependabot.py not found -- clone the agent_rules repo as a sibling" >&2
        exit 2
    fi
    ../agent_rules/run_shared_script.py --check-failed-exit 3 -- ../agent_rules/apply_dependabot.py . {{args}}

# Apply this repo's Dependabot security fixes, then upgrade every other dependency locally,
# one tested commit each. Never pushes.
update-deps *args:
    #!/usr/bin/env bash
    set -euo pipefail
    if [[ ! -x ../agent_rules/update_deps.py ]]; then
        echo "error: ../agent_rules/update_deps.py not found -- clone the agent_rules repo as a sibling" >&2
        exit 2
    fi
    ../agent_rules/run_shared_script.py --check-failed-exit 3 -- ../agent_rules/update_deps.py . {{args}}

# END FLEET RECIPES (CORE)

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

# Run linting and tests (pre-commit check)
# This Justfile is the Single Source Of Truth (SSOT) for all pre-commit checks.
# No additional linting or testing logic should be added anywhere else (e.g. CI configs).
precommit: precommit-fleet
    #!/usr/bin/env bash
    if [[ "$(git config core.hooksPath 2>/dev/null)" != ".fleet/git_hooks" ]]; then
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

# BEGIN FLEET RECIPES (SCRIPTS)
# Generated from agent_rules payload/scripts/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Analyse project source files to evaluate AI agent readiness
analyse-ai-readiness *args:
    @{{uv_run}} .fleet/scripts/analyse_ai_readiness.py {{args}}

# Check source file size thresholds for AI agent readiness (fails if threshold breached)
check-ai-readiness *args:
    @{{uv_run}} .fleet/scripts/analyse_ai_readiness.py --fail-on {{args}}

# END FLEET RECIPES (SCRIPTS)

# BEGIN FLEET RECIPES (GIT_HOOKS)
# Generated from agent_rules payload/git_hooks/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Sets this repo's own local git config to prefer linear history, overriding whatever
# a clone's global config says. `pull.rebase` and `merge.ff` live in .git/config, which
# git deliberately never lets a repo commit -- so this is the one-off `setup-git-hooks`
# already asks a fresh clone to run, not something a sync can write for you. Actual
# enforcement (for a clone that skips this, or whose global config wins some other way)
# is the `pre-merge-commit` and `pre-push` hooks in .fleet/git_hooks/, which reject merge
# commits regardless of what these two settings say.
setup-linear-history:
    @git config pull.rebase true
    @git config merge.ff only
    @echo "Linear history preferences set for this clone"

# Refuses rather than clobbers. git reads exactly one hooks directory, so silently
# overwriting core.hooksPath disables whatever was there -- which is precisely how four
# repos lost their beads integration without a word (ar-x4l). `bd init` does exactly
# this, so the refusal is needed; `check-git-hooks-active` is what reports it if bd wins the
# race anyway. An unset value and the legacy `.githooks` are both safe to replace.
#
# Point git at .fleet/git_hooks/, so `just precommit` runs before each commit here.
setup-git-hooks:
    #!/usr/bin/env bash
    set -euo pipefail
    current=$(git config core.hooksPath || true)
    if [ -n "$current" ] && [ "$current" != ".githooks" ] && [ "$current" != ".fleet/git_hooks" ]; then
        echo "core.hooksPath is already $current -- refusing to overwrite it." >&2
        echo "git reads one hooks directory only; merge the two before setting this." >&2
        exit 1
    fi
    git config core.hooksPath .fleet/git_hooks
    echo "Git hooks set up"

# END FLEET RECIPES (GIT_HOOKS)

# BEGIN FLEET RECIPES (GITHUB)
# Generated from agent_rules payload/github/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# zizmor's version is agent_rules' locked one, stamped in by the sync, so update-deps there
# upgrades it fleet-wide. --offline keeps the audit reproducible and token-free in the git hook;
# known-vulnerable actions reach the fleet through Dependabot security updates instead. zizmor
# exits 3 when it collects no input, which is a repo with no workflows, actions or dependabot.yml.
#
# Audit this repo's GitHub Actions workflows, composite actions and dependabot.yml with zizmor.
lint-workflows:
    #!/usr/bin/env bash
    set -uo pipefail
    status=0
    uvx zizmor@1.32.0 --offline . || status=$?
    if [ "$status" -eq 3 ]; then
        echo "lint-workflows: nothing to audit"
        exit 0
    fi
    exit "$status"

# END FLEET RECIPES (GITHUB)

# BEGIN FLEET RECIPES (RULES)
# Generated from agent_rules payload/rules/recipes.just. Do not edit inside this block:
#      edit it there, then run `just sync` in agent_rules.

# Fail if a generated Beads integration block has reappeared in the repo's root markdown.
fleet-gate-rules:
    @uv run --script .fleet/rules/check_beads_block.py

# END FLEET RECIPES (RULES)
