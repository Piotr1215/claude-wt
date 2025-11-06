# claude-wt

[![CI](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml/badge.svg)](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/anthropics/claude-wt/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/claude-wt)
[![PyPI version](https://badge.fury.io/py/claude-wt.svg)](https://badge.fury.io/py/claude-wt)

Manage multiple Claude Code sessions in parallel using git worktrees. Fast session creation, instant switching, zero conflicts.

## Installation

### Requirements

- Python 3.12+
- Git with worktree support
- [Claude Code CLI](https://docs.claude.com/en/docs/claude-code) (launches automatically in each worktree)
- [fzf](https://github.com/junegunn/fzf) (for `switch` and `clean` commands)

Optional:
- tmux (for automatic session management - highly recommended)

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
# Create new session (launches Claude with your query)
claude-wt new "implement user authentication"

# Create session with prompt from file
claude-wt new my-feature -f ~/prompts/detailed-task.txt

# Switch between sessions (launches fresh Claude session by default)
claude-wt switch

# Switch and resume previous conversation
claude-wt switch --continue

# List active sessions
claude-wt list

# Clean up
claude-wt clean
```

## Commands

### Core Workflow

**`new [name]`** - Create worktree session and launch Claude
```bash
claude-wt new "fix parser"              # Launches Claude with query
claude-wt new --name parser-fix         # Named branch
claude-wt new --branch develop          # From specific branch
claude-wt new --pull                    # Pull latest first
claude-wt new task -f ~/prompt.txt      # Load prompt from file (-f or --prompt-file)
```

Claude is launched with `--dangerously-skip-permissions --add-dir <repo>` for automated workflows.

**`switch [--continue]`** - Switch sessions (fzf picker)
```bash
claude-wt switch              # Fresh Claude session (default)
claude-wt switch --continue   # Resume previous conversation
```

**`list`** - Show all worktrees

**`clean [name]`** - Remove worktrees
```bash
claude-wt clean                         # Interactive picker
claude-wt clean session-name            # Specific session
claude-wt clean --all                   # All sessions
```

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

Creates git worktrees in a sibling directory `{repo-name}-worktrees/`. Each worktree gets its own branch, runs in a dedicated tmux session, and automatically launches Claude Code.

Benefits:
- **Auto-launches Claude** - No manual setup needed
- **Parallel sessions** - Work on multiple features simultaneously
- No git pull delays - sessions start instantly
- No conflicts - each session is isolated
- Clean history - main branch stays pristine
- Fast switching - fzf fuzzy search, fresh Claude session each switch
- Automatic cleanup - one command removes everything

## Tmux Integration

When run from tmux:
- Creates dedicated session per worktree
- Automatically switches to new session
- Launches Claude Code in the session
- All panes/windows start in worktree directory

```bash
claude-wt new "auth feature" --name auth
# Creates: ../repo-worktrees/claude-wt-auth/
# Tmux session: wt-auth
# Auto-switches to session
# Launches: claude --dangerously-skip-permissions --add-dir <repo> -- "auth feature"
```

When not in tmux, Claude launches directly in the current terminal.

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
