# Shell Integration for Claude-wt Worktrees

This directory contains shell integration scripts to help you identify when you're working in a worktree.

## Problem

When working in git worktrees, it's easy to forget you're in an isolated environment and accidentally try to switch branches, which causes file corruption and lost work.

## Solution

Add a visual indicator to your shell prompt that shows when you're in a worktree.

## Installation Options

### Option 1: Basic Bash/Zsh Prompt

Add to your `~/.zshrc` or `~/.bashrc`:

```bash
# Source the worktree prompt script
source /path/to/claude-wt/shell/worktree-prompt.sh

# Add to your prompt (zsh)
PS1='$(claude_wt_prompt)'$PS1

# Add to your prompt (bash)
PS1='$(claude_wt_prompt)\$ '
```

This will show `🌳[WT:branch-name]` when you're in a worktree.

### Option 2: Starship (Recommended)

If you use [Starship](https://starship.rs/) prompt, add this to your `~/.config/starship.toml`:

```toml
# Copy the content from starship-worktree.toml
[custom.claude_wt]
command = """
if [ -f .git ] && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    if [[ "$PWD" == *"-worktrees/"* ]]; then
        basename "$PWD"
    else
        git rev-parse --abbrev-ref HEAD
    fi
fi
"""
when = '[ -f .git ]'
format = '🌳[$output]($style) '
style = 'bold yellow'
```

### Option 3: Oh My Zsh Theme

If you use Oh My Zsh, add this to your custom theme file:

```bash
# Add to ~/.oh-my-zsh/custom/themes/your-theme.zsh-theme
source /path/to/claude-wt/shell/worktree-prompt.sh

# Modify your PROMPT to include:
PROMPT='$(claude_wt_prompt)'$PROMPT
```

## Testing

After installation:

1. Go to a regular git repo:
   ```bash
   cd ~/dev/your-project
   # Your prompt should look normal
   ```

2. Create and enter a worktree:
   ```bash
   claude-wt new "test"
   # Your prompt should now show: 🌳[WT:claude-wt-test]
   ```

3. Try to switch branches (this will now be obvious you're in a worktree):
   ```bash
   git checkout main  # You'll see the worktree indicator and get an error from the hook
   ```

## What You'll See

- **Normal repo**: No indicator
- **In worktree**: `🌳[WT:branch-name]` in bold yellow
- **Starship users**: Tree emoji with branch name

This visual reminder helps prevent the common mistake of trying to switch branches while in a worktree!
