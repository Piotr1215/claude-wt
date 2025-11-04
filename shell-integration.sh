#!/usr/bin/env bash
# Claude-wt Shell Integration
# Source this file in your ~/.bashrc or ~/.zshrc:
#   source /path/to/claude-wt/shell-integration.sh

# Convenient aliases
alias cw='claude-wt'
alias cwn='claude-wt new'
alias cws='claude-wt switch'
alias cwl='claude-wt list'
alias cwst='claude-wt status'
alias cwc='claude-wt clean'

# Quick session creation with common patterns
cwq() {
    # Quick new session with query
    claude-wt new "$*"
}

cwcd() {
    # Change to a worktree directory
    local session="$1"
    if [ -z "$session" ]; then
        echo "Usage: cwcd <session-name>"
        return 1
    fi

    # Get repo root
    local repo_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [ -z "$repo_root" ]; then
        echo "Error: Not in a git repository"
        return 1
    fi

    # Calculate worktree path
    local repo_name=$(basename "$repo_root")
    local worktree_base=$(dirname "$repo_root")/${repo_name}-worktrees
    local worktree_path="${worktree_base}/claude-wt-${session}"

    if [ -d "$worktree_path" ]; then
        cd "$worktree_path"
        echo "Changed to worktree: $worktree_path"
        claude-wt status
    else
        echo "Error: Worktree not found: $worktree_path"
        return 1
    fi
}

# Tmux integration - create session and switch
cwt() {
    # Create worktree in tmux session
    local query="$*"
    local timestamp=$(date +%Y%m%d-%H%M%S)

    # Create worktree
    local wt_path=$(claude-wt new --print-path --name "$timestamp" "$query")

    if [ -n "$wt_path" ]; then
        # Create tmux session
        local session_name="wt-${timestamp}"
        tmux new-session -d -s "$session_name" -c "$wt_path"

        # Launch claude in the session
        tmux send-keys -t "$session_name" "claude --continue" Enter

        # Switch to the session
        if [ -n "$TMUX" ]; then
            tmux switch-client -t "$session_name"
        else
            tmux attach -t "$session_name"
        fi
    fi
}

# Bash/Zsh completion for session names
_claude_wt_sessions() {
    local cur="${COMP_WORDS[COMP_CWORD]}"
    local sessions=$(git worktree list --porcelain 2>/dev/null | \
        grep "^branch" | \
        grep "claude-wt-" | \
        sed 's/^branch refs\/heads\/claude-wt-//')
    COMPREPLY=( $(compgen -W "${sessions}" -- ${cur}) )
}

# Register completion
if [ -n "$BASH_VERSION" ]; then
    complete -F _claude_wt_sessions cwcd
    complete -F _claude_wt_sessions 'claude-wt resume'
    complete -F _claude_wt_sessions 'claude-wt clean'
fi

# PS1 integration - show when in a claude-wt worktree
claude_wt_ps1() {
    local branch=$(git branch --show-current 2>/dev/null)
    if [[ "$branch" == claude-wt-* ]]; then
        local session="${branch#claude-wt-}"
        echo "[wt:$session]"
    fi
}

# Optional: Add to your PS1
# export PS1="\$(claude_wt_ps1)$PS1"

echo "Claude-wt shell integration loaded!"
echo ""
echo "Available commands:"
echo "  cw         - claude-wt (main command)"
echo "  cwn        - New session"
echo "  cws        - Switch sessions (fzf)"
echo "  cwl        - List sessions"
echo "  cwst       - Show status"
echo "  cwc        - Clean sessions"
echo "  cwq        - Quick new with query"
echo "  cwcd       - CD to worktree"
echo "  cwt        - New session in tmux"
echo ""
echo "Example: cwn 'fix authentication bug'"
