# Install/update claude-wt locally
install:
    uv tool install -e . --python 3.12 --reinstall

# Run tests
test:
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