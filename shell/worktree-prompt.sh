#!/usr/bin/env bash
# Claude-wt worktree shell indicator
# Source this in your ~/.zshrc or ~/.bashrc to get a visual indicator when in a worktree
#
# Usage (zsh):
#   source /path/to/worktree-prompt.sh
#   PS1='$(claude_wt_prompt)'$PS1
#
# Usage (bash):
#   source /path/to/worktree-prompt.sh
#   PS1='$(claude_wt_prompt)\$ '

claude_wt_prompt() {
    # Check if we're in a git repository
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        return
    fi

    # Check if this is a worktree (has .git file, not .git directory)
    if [ -f .git ]; then
        # Get the branch name
        local branch=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)

        # Check if we're in a -worktrees directory
        if [[ "$PWD" == *"-worktrees/"* ]]; then
            # Extract worktree name from path
            local wt_name=$(basename "$PWD")
            echo "🌳[WT:$wt_name] "
        else
            # Generic worktree indicator
            echo "🌳[WORKTREE:$branch] "
        fi
    fi
}

# For starship users - detect worktrees
claude_wt_check() {
    if [ -f .git ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        echo "worktree"
    fi
}
