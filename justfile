# Install/update claude-wt locally
install:
    uv tool install -e . --python 3.12 --reinstall

# Run all tests with pytest
test:
    uv run pytest

# Run tests with coverage report
test-cov:
    uv run pytest --cov=claude_wt --cov-report=term-missing

# Run tests in verbose mode
test-verbose:
    uv run pytest -vv

# Run specific test file or pattern
test-match pattern:
    uv run pytest -k "{{pattern}}"

# Run tests and show output (including print statements)
test-debug:
    uv run pytest -s -vv

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

# Install and test
update: install test