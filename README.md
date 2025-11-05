# claude-wt

[![CI](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml/badge.svg)](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/anthropics/claude-wt/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/claude-wt)
[![PyPI version](https://badge.fury.io/py/claude-wt.svg)](https://badge.fury.io/py/claude-wt)

Manage multiple Claude Code sessions in parallel using git worktrees. Fast session creation, instant switching, zero conflicts.

## Installation

### Requirements

- Python 3.12+
- Git with worktree support
- [fzf](https://github.com/junegunn/fzf) (for `switch` and `clean` commands)

Optional:
- tmux (for automatic session management)
- Claude CLI (if you want to launch Claude automatically)

### Install

```bash
uv tool install claude-wt
```

Or use without installing:
```bash
uvx claude-wt new "implement auth"
```

## Quick Start

```bash
# Create new session
claude-wt new "implement user authentication"

# Switch between sessions
claude-wt switch

# List active sessions
claude-wt list

# Clean up
claude-wt clean
```

## Commands

### Core Workflow

**`new [name]`** - Create worktree session
```bash
claude-wt new "fix parser"              # Timestamped branch
claude-wt new --name parser-fix         # Named branch
claude-wt new --branch develop          # From specific branch
claude-wt new --pull                    # Pull latest first
```

**`switch`** - Switch sessions (fzf picker)

**`list`** - Show all worktrees

**`clean [name]`** - Remove worktrees
```bash
claude-wt clean                         # Interactive picker
claude-wt clean session-name            # Specific session
claude-wt clean --all                   # All sessions
```

**`status`** - Show current worktree context

**`init`** - Add worktrees to .gitignore

### Integrations

**`linear-issue ISSUE-ID`** - Create worktree from Linear issue (for taskwarrior hooks)

**`from-pr [PR-NUMBER]`** - Create worktree from GitHub PR

**`from-pr-noninteractive PR-NUMBER`** - Non-interactive PR worktree (for automation)

## Shell Completion

```bash
# Install zsh completion
claude-wt install-completion

# Add to ~/.zshrc if not present:
fpath=(~/.zsh/completions $fpath)
autoload -Uz compinit && compinit

# Reload
exec zsh
```

Now tab completion works everywhere:
```bash
claude-wt <TAB>              # Shows commands
claude-wt new --<TAB>        # Shows flags
claude-wt clean --<TAB>      # Shows options
```

## How It Works

Creates git worktrees in a sibling directory `{repo-name}-worktrees/`. Each worktree gets its own branch and runs in a dedicated tmux session.

Benefits:
- No git pull delays - sessions start instantly
- No conflicts - each session is isolated
- Clean history - main branch stays pristine
- Fast switching - fzf fuzzy search
- Automatic cleanup - one command removes everything

## Tmux Integration

When run from tmux:
- Creates dedicated session per worktree
- Automatically switches to new session
- All panes/windows start in worktree directory

```bash
claude-wt new "auth feature" --name auth
# Creates: ../repo-worktrees/claude-wt-auth/
# Tmux session: wt-auth
# Auto-switches to session
```

## Development

```bash
git clone https://github.com/anthropics/claude-wt.git
cd claude-wt
uv sync
uv run claude-wt --help
```

Run tests:
```bash
uv run pytest
```

## License

MIT
