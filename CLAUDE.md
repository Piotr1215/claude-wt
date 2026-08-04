# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Claude-wt is a Python CLI tool that manages isolated git worktrees for running multiple Claude Code sessions in parallel. It prevents conflicts when Claude works on different features simultaneously by creating separate branches and worktrees for each session.

## Development Setup

### Install locally for development
```bash
uv tool install -e . --python 3.12 --reinstall
```

### Install from source without modifying global environment
```bash
uvx --from . claude-wt --help
```

### Run tests and verify installation
```bash
just test  # Runs version and help commands
```

### Use the justfile for common tasks
```bash
just install  # Install locally
just test     # Run basic tests
just clean-all  # Clean all worktrees
just list     # List active worktrees
just update   # Install and test in one command
```

## Architecture

### Core Components

The entire application is implemented in a single file `claude_wt/cli.py` (~1400 lines) using:
- **cyclopts** - CLI argument parsing and command routing
- **rich** - Terminal UI with colored output, panels, and tables
- **subprocess** - All git operations and external command execution
- **pathlib** - Cross-platform path handling

### Key Commands

1. **linear_issue** - Smart Linear issue handler (NEW - primary command for taskwarrior):
   - Handles ALL complex logic for issue management
   - Checks existing branches/worktrees and prompts for selection
   - Creates worktrees in external sibling directories
   - Supports both interactive and non-interactive modes
   - Can create and manage tmux sessions automatically

2. **new** - Creates a new worktree branch and launches Claude
   - Generates timestamped or custom branch names (`claude-wt-{suffix}`)
   - Creates worktree in external sibling directory
   - Launches Claude via custom monitor script

3. **resume** - Resumes an existing Claude session with `--continue` flag

4. **from_issue** - Interactive Linear integration (legacy, use linear_issue instead)

5. **from_issue_noninteractive** - Programmatic Linear integration (DEPRECATED, kept for compatibility)

6. **clean** / **clean_issue** - Removes worktrees and optionally branches

### External Worktree Architecture

**IMPORTANT CHANGE**: Worktrees are now created in SIBLING directories to prevent Claude confusion:

```
~/loft/
    vcluster-docs/                    # Main repository
    vcluster-docs-worktrees/           # External worktrees (sibling directory)
        ├── doc-975-config-ref/        # Issue worktree
        ├── doc-980-api-docs/          # Issue worktree
        └── claude-wt-20241201/        # Timestamp worktree

~/dev/
    my-project/                        # Main repository
    my-project-worktrees/              # External worktrees (sibling directory)
        └── eng-123-auth-fix/          # Issue worktree
```

Benefits:
- Claude always knows it's in a worktree (path is explicit)
- No confusion with main repo files
- Clean separation of concerns
- Easy to manage and clean up

Each worktree:
- Has its own branch tracking changes
- Contains a CLAUDE.md file explaining the worktree context
- Shares the same git repository objects
- Allows parallel Claude sessions without conflicts

### Linear Integration

For Linear issue management:
- Requires `LINEAR_API_KEY` and `LINEAR_USER_ID` environment variables
- Fetches assigned issues via GraphQL API
- Creates branches following pattern: `{issue-id}/{user-chosen-suffix}`
- Launches Claude with full issue context

### External Dependencies

The tool integrates with external scripts (hardcoded paths):
- `/home/decoder/.claude/scripts/__claude_with_monitor.sh` - Claude launcher
- `/home/decoder/dev/dotfiles/scripts/__get_linear_issue.sh` - Issue detail fetcher

## Taskwarrior Integration

The primary use case for claude-wt is integration with Taskwarrior via the `+wt` tag:

### Setup
1. Install the simplified hook: `cp taskwarrior-hook-simple.py ~/.task/hooks/on-modify-worktree.py`
2. Make it executable: `chmod +x ~/.task/hooks/on-modify-worktree.py`
3. Configure task UDAs:
   ```bash
   task config uda.linear_id.type string
   task config uda.linear_id.label "Linear ID"
   task config uda.repo_path.type string
   task config uda.repo_path.label "Repository"
   task config uda.worktree_path.type string
   task config uda.worktree_path.label "Worktree"
   ```

### Usage
```bash
# Create a task with +wt tag
task add "Fix documentation" +wt project:vdocs linear_id:DOC-975

# Starting the task triggers worktree creation
task start <id>  # Prompts for branch selection/creation, launches Claude in tmux

# Resume later
task start <id>  # Resumes in existing worktree
```

### How It Works
1. The hook detects `+wt` tag when task starts
2. Calls `claude-wt linear_issue` with the Linear ID
3. claude-wt handles ALL complex logic:
   - Checks for existing branches/worktrees
   - Prompts for selection or new branch name
   - Creates external worktree
   - Sets up tmux session with Claude
   - Returns worktree path for future use

## Common Development Tasks

### Adding a new command
1. Add a new `@app.command` decorated function in `cli.py`
2. Use `console.print()` for output (not print())
3. Handle errors with try/except and proper exit codes
4. Use subprocess for git operations

### Working with git operations
- Always use `subprocess.run()` with `check=True` for git commands
- Capture output with `capture_output=True, text=True`
- Get repo root: `git rev-parse --show-toplevel`
- Check current branch: `git branch --show-current`
- List worktrees: `git worktree list --porcelain`

### UI patterns
- Use Rich panels for important messages
- Color coding: green (success), yellow (warning), red (error), cyan (info)
- Tables for listing operations
- Status indicators with emojis when appropriate

## Testing Approach

Currently no automated tests. Manual testing involves:
1. `just test` - Verifies CLI is installed and responds
2. Create test worktrees with `claude-wt new "test"`
3. List with `claude-wt list`
4. Clean with `claude-wt clean --all`

## Important Implementation Details

1. **Gitignore Check** - `check_gitignore()` validates `.claude-wt/worktrees` is ignored before creating worktrees. Checks local, global, and custom git exclude files.

2. **Branch Naming** - All branches are prefixed with `claude-wt-` except Linear issue branches which use `{issue-id}/{suffix}` format.

3. **Worktree Path Sanitization** - Forward slashes in branch names are replaced with hyphens for filesystem compatibility.

4. **Error Handling** - All subprocess calls wrapped in try/except with user-friendly error messages via Rich console.

5. **Non-interactive Mode** - `from_issue_noninteractive` outputs only worktree path to stdout for parsing by automation hooks.

## Dependencies

Python 3.12+ required. Key packages:
- cyclopts >= 3.0.0 (CLI framework)
- rich >= 13.0.0 (Terminal UI)
- uv-dynamic-versioning (version management)

Development dependencies:
- pre-commit >= 4.2.0
- pyright >= 1.1.402 (type checking)