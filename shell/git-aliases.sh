#!/usr/bin/env bash
# Safe git aliases that prevent branch switching in worktrees
# Add to ~/.bashrc or ~/.zshrc

# Check if in a worktree
__in_worktree() {
    [ -f .git ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1
}

# Safe git checkout
gco() {
    if __in_worktree && [[ "$PWD" == *"-worktrees/"* ]]; then
        echo "🚨 ERROR: You're in a worktree! Use 'cd' to switch context instead."
        echo "Current worktree: $(basename "$PWD")"
        echo ""
        echo "To switch:"
        echo "  claude-wt switch"
        echo "  cd /path/to/main/repo"
        return 1
    fi
    git checkout "$@"
}

# Safe git switch
gsw() {
    if __in_worktree && [[ "$PWD" == *"-worktrees/"* ]]; then
        echo "🚨 ERROR: You're in a worktree! Use 'cd' to switch context instead."
        echo "Current worktree: $(basename "$PWD")"
        echo ""
        echo "To switch:"
        echo "  claude-wt switch"
        echo "  cd /path/to/main/repo"
        return 1
    fi
    git switch "$@"
}

# Export functions
export -f gco gsw
