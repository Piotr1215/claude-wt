# Install/update claude-wt locally as a tool
install:
    uv tool install -e . --python 3.12 --reinstall

# Install/update claude-wt in development mode (for testing)
install-dev:
    uv pip install --editable . --force-reinstall

# Run all tests with pytest
test:
    uv run --dev --with pytest pytest

# Run tests with coverage report
test-cov:
    uv run --dev --with pytest --with pytest-cov pytest --cov=claude_wt --cov-report=term-missing

# Run tests in verbose mode
test-verbose:
    uv run --dev --with pytest pytest -vv

# Run specific test file or pattern
test-match pattern:
    uv run --dev --with pytest pytest -k "{{pattern}}"

# Run tests and show output (including print statements)
test-debug:
    uv run --dev --with pytest pytest -s -vv

# Quick smoke test - check CLI works
test-cli:
    claude-wt version
    claude-wt --help

# Clean all worktrees
clean-all:
    claude-wt clean --all

# List worktrees
list:
    claude-wt list

# Commit changes
commit message:
    git add -A
    git commit -m "{{message}}"

# Install as tool and test
update: install test

# Install in dev mode and test
update-dev: install-dev test

# Run all static analysis checks (matches CI)
lint:
    uv run --dev pre-commit run --all-files

# Run only ruff linting checks
lint-ruff:
    uv run --dev ruff check claude_wt/

# Run ruff formatting check
format-check:
    uv run --dev ruff format --check claude_wt/

# Auto-format code with ruff
format:
    uv run --dev ruff format claude_wt/

# Fix auto-fixable lint issues
fix:
    uv run --dev ruff check --fix claude_wt/

# Run type checking with pyright
typecheck:
    uv run --dev pyright claude_wt/

# Run all checks (lint + typecheck)
check: lint typecheck

# Quick check - run static analysis on changed files only
check-quick:
    uv run --dev pre-commit run

# Install pre-commit hooks (may fail if core.hooksPath is set)
install-hooks:
    uv run --dev pre-commit install || echo "Note: pre-commit hooks not installed due to git config"

# Sync dev dependencies
sync-dev:
    uv sync --dev