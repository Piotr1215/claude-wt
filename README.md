# Claude-Worktree

[![CI](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml/badge.svg)](https://github.com/anthropics/claude-wt/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/anthropics/claude-wt/branch/main/graph/badge.svg)](https://codecov.io/gh/anthropics/claude-wt)
[![PyPI version](https://badge.fury.io/py/claude-wt.svg)](https://badge.fury.io/py/claude-wt)

**The fastest way to run multiple Claude Code sessions in parallel.** Built for tmux users who want instant context switching between AI-assisted coding sessions.

Creates isolated git worktrees in seconds, so you can:
- 🚀 Launch new sessions instantly (no slow git pulls!)
- 🔄 Switch between sessions with fuzzy search
- 📍 Always know which worktree you're in
- 🧹 Clean up with one command

*Inspired by a script from [aaazzam](https://github.com/aaazzam).*

## Quick Start

Jump right in without installing anything:

```bash
uvx claude-wt new "implement user authentication"
```

**That's it.** You're now working in a clean branch where Claude can't mess up your pristine codebase.

### Installation Options

If you prefer global installation:

```bash
uv tool install claude-wt
```

Or from source:

```bash
git clone https://github.com/anthropics/claude-wt.git
cd claude-wt
uv install -e .
```

## Commands

### ⚡ Quick Start: `new`

Spin up a new isolated Claude session **instantly**:

```bash
claude-wt new "implement user authentication"
```

Behind the scenes: creates a timestamp branch, sets up a worktree in a sibling directory `{repo-name}-worktrees/`, and launches Claude with your query.

**Pro tip:** It skips git pull by default for speed! Add `--pull` if you need latest changes.

Want a memorable branch name? Use `--name`:

```bash
claude-wt new "fix the parser" --name parser-fix
```

Need to branch from a specific source? Use `--branch`:

```bash
claude-wt new "hotfix for prod" --branch main --name hotfix-123
```

### 🔄 Instant Switch: `switch`

**New!** The fastest way to jump between sessions using fuzzy search:

```bash
claude-wt switch
```

Uses fzf to show all your sessions - just type to filter and hit Enter to resume!

### 📍 Know Where You Are: `status`

**New!** See your current worktree context at a glance:

```bash
claude-wt status
```

Shows:
- Which session you're in
- Branch name and location
- Quick commands for what to do next

### 📋 See What's Running: `list`

See all your active worktrees in a nice table:

```bash
claude-wt list
```

Shows each session with its health status and path.

### ⏸️ Pick Up Where You Left Off: `resume`

Resume a specific session:

```bash
claude-wt resume 20241201-143022
```

Or just use `claude-wt switch` for fuzzy search!

### 🧹 Clean Up: `clean`

Remove a specific session when you're done:

```bash
claude-wt clean 20241201-143022
```

Or clean everything:

```bash
claude-wt clean --all  # The Marie Kondo approach
```

## Taskwarrior Integration

Claude-wt integrates seamlessly with Taskwarrior for task-driven development:

```bash
# Create a task with Linear issue
task add "Fix documentation" +wt linear_id:DOC-975 project:myproject

# Starting the task creates/resumes the worktree
task start <id>
```

The included Taskwarrior hook (`taskwarrior-hook-simple.py`) automatically handles worktree creation and Claude session management.

## Tmux Integration

Claude-wt is designed for tmux power users. When you create a new worktree from within tmux:

- **Dedicated tmux session**: Creates a new tmux session named `wt-{name}` for each worktree
- **Automatic session switching**: Switches you to the new session immediately
- **Correct working directory**: The entire session runs in the worktree directory
- **All panes/windows start in the right place**: Any new panes or windows you create will be in the worktree

Example workflow:
```bash
# Create a new worktree (from within tmux)
claude-wt new "implement authentication" --name auth

# This automatically:
# 1. Creates worktree at ../repo-worktrees/claude-wt-auth/
# 2. Creates tmux session "wt-auth" with that as working directory
# 3. Launches Claude in the session
# 4. Switches you to the new session

# Later, you can switch back to this session:
tmux switch-client -t wt-auth
# Or just use: claude-wt switch
```

## Shell Integration

**New!** Add convenient aliases and functions to your shell. Source the integration script in your `~/.bashrc` or `~/.zshrc`:

```bash
source /path/to/claude-wt/shell-integration.sh
```

This gives you:

```bash
# Quick aliases
cw          # claude-wt (main command)
cwn         # New session
cws         # Switch sessions (fzf)
cwl         # List sessions
cwst        # Show status
cwc         # Clean sessions

# Useful functions
cwq "task"  # Quick new session with query
cwcd auth   # CD to worktree directory
cwt "task"  # Create session + tmux integration

# Tab completion for session names
cwcd <TAB>  # Shows all available sessions
```

Example daily workflow:
```bash
# Morning: start new feature
cwn "add user profiles" --name profiles

# Check what's running
cwl

# Quick switch to another session
cws  # fuzzy search with fzf

# Jump into worktree directory
cwcd profiles

# Done? Clean up
cwc profiles
```

## How It Works

Think of it like having multiple parallel universes for your code:

1. **Branch Creation** → Each session gets its own branch (`claude-wt-{timestamp}` or your custom name)
2. **Worktree Setup** → Creates a separate directory in `{repo-name}-worktrees/` sibling directory so files don't conflict
3. **Claude Launch** → Starts Claude in the isolated environment with full repo access
4. **Tmux Integration** → Automatically sets up your tmux session to work in the worktree
5. **Session Management** → Resume, list, and clean up sessions effortlessly

## Why You'll Love This

- **⚡ Blazing Fast** → No slow git pulls, sessions start instantly
- **🎯 Zero Friction** → Fuzzy search to switch, status to orient, one command to clean up
- **🔒 Fear-Free** → Claude can't break your main branch even if it tries
- **🧠 Mental Clarity** → Always know which worktree you're in
- **🚀 Context Switching** → Jump between sessions in under a second
- **🧹 Easy Cleanup** → One command to remove experimental branches
- **📦 Clean History** → Your main branch stays pristine for serious work

## What You Need

- **Python 3.12+**
- **Git with worktree support** (any recent version)
- **Claude CLI** (installed and authenticated)

## Development

Uses uv for dependency management:

```bash
uv sync
uv run claude-wt --help
```

Or test changes without installing:

```bash
uvx --from . claude-wt --help
```

---

*Built with the assumption that your Claude sessions shouldn't be a game of git-roulette with your main branch.*