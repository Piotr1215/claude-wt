"""Core utilities for claude-wt.

Shared functions for path management, git operations, and worktree detection.
"""

from pathlib import Path


def get_worktree_base(repo_root: Path) -> Path:
    """Get the external worktree base directory (sibling to repo)."""
    repo_name = repo_root.name
    return repo_root.parent / f"{repo_name}-worktrees"


def is_claude_wt_worktree(worktree: dict) -> bool:
    """Check if a worktree is a claude-wt worktree.

    Checks both branch name (starts with 'claude-wt-') and path
    (contains '-worktrees/claude-wt-' for external worktrees).

    Parameters
    ----------
    worktree : dict
        Worktree dict with 'branch' and 'path' keys

    Returns
    -------
    bool
        True if this is a claude-wt worktree
    """
    branch_name = worktree.get("branch", "")
    wt_path = worktree.get("path", "")

    return branch_name.startswith("claude-wt-") or "-worktrees/claude-wt-" in wt_path


def create_worktree_context(
    wt_path: Path, issue_id: str, branch_name: str, repo_root: Path
):
    """Create a CLAUDE.md file specific to this worktree."""
    claude_md = wt_path / "CLAUDE.md"

    content = f"""# Worktree Context

🚨 **CRITICAL: You are in a Git WORKTREE - NEVER switch branches here!** 🚨

## ⚠️ IMPORTANT RULES ⚠️

### ❌ NEVER DO THIS:
- **NEVER switch branches** in this worktree (with git checkout, git switch, or lazygit)
- **NEVER run git checkout/switch** - this will corrupt your work!
- **This worktree is LOCKED to branch `{branch_name}`**

### ✅ INSTEAD DO THIS:
- To work on a different branch: **`cd` to a different worktree** or back to main repo
- To switch context: Use `claude-wt switch` or `cd {repo_root}`
- To see all worktrees: Run `claude-wt list`

## Location Information
- **Current Worktree**: `{wt_path}`
- **Main Repository**: `{repo_root}`
- **Locked Branch**: `{branch_name}`
- **Issue/Session**: {issue_id}

## Why Worktrees?
Each worktree is permanently locked to ONE branch. This allows multiple parallel work sessions
without conflicts. Think of it as a separate checkout, not as a place to switch branches.

## Workflow
```bash
# ✅ Work on current branch
git add .
git commit -m "fix: implement feature"
git push origin {branch_name}

# ✅ Switch to different worktree
cd {repo_root}  # Go back to main
claude-wt switch  # Pick different worktree

# ❌ NEVER do this in a worktree
git checkout main  # THIS BREAKS EVERYTHING!
git switch other-branch  # DON'T DO THIS!
```

## Remember
**This worktree = One branch only**
Path: {wt_path}
Branch: {branch_name}

To work on something else, use a different worktree or go back to main repo.
"""
    claude_md.write_text(content)


def install_branch_protection_hook(wt_path: Path, branch_name: str):
    """Install a post-checkout hook that prevents branch switching in worktrees."""
    try:
        # In worktrees, .git is a file that points to the actual git directory
        git_path = wt_path / ".git"

        if not git_path.exists():
            return  # No .git file/dir, skip hook installation (likely in tests)

        if git_path.is_file():
            # Read the gitdir path from the .git file
            git_content = git_path.read_text().strip()
            if git_content.startswith("gitdir: "):
                gitdir_str = git_content[8:]  # Remove "gitdir: " prefix
                # Handle both absolute and relative paths
                gitdir = Path(gitdir_str)
                if not gitdir.is_absolute():
                    gitdir = (wt_path / gitdir).resolve()
                hooks_dir = gitdir / "hooks"
            else:
                return  # Invalid .git file, skip hook installation
        else:
            # Regular repo (not a worktree)
            hooks_dir = git_path / "hooks"

        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path = hooks_dir / "post-checkout"

        # Create hook that detects and prevents branch switches
        hook_content = f"""#!/usr/bin/env bash
# Claude-wt worktree protection hook
# This worktree is locked to branch: {branch_name}

prev_head="$1"
new_head="$2"
branch_checkout="$3"

# Only check on branch switches (not file checkouts)
if [ "$branch_checkout" = "1" ]; then
    current_branch=$(git rev-parse --abbrev-ref HEAD)

    if [ "$current_branch" != "{branch_name}" ]; then
        echo ""
        echo "🚨🚨🚨 WORKTREE BRANCH SWITCH DETECTED! 🚨🚨🚨"
        echo ""
        echo "ERROR: You tried to switch away from branch '{branch_name}'"
        echo "Current branch is now: $current_branch"
        echo ""
        echo "⚠️  This worktree is LOCKED to branch: {branch_name}"
        echo "⚠️  Switching branches in a worktree causes file corruption and lost work!"
        echo ""
        echo "What you should do instead:"
        echo "  1. Switch back: git checkout {branch_name}"
        echo "  2. To work on '$current_branch': cd to main repo or different worktree"
        echo "  3. Use: claude-wt switch (to switch between worktrees)"
        echo "  4. Use: claude-wt list (to see all worktrees)"
        echo ""
        echo "Switching back to {branch_name} now..."
        echo ""

        # Automatically switch back to the correct branch
        git checkout {branch_name} 2>/dev/null

        exit 1
    fi
fi

exit 0
"""

        hook_path.write_text(hook_content)
        hook_path.chmod(0o755)  # Make executable

    except Exception:
        # Silently fail if hook installation doesn't work (e.g., in tests or restricted environments)
        pass


def check_gitignore(repo_root: Path) -> bool:
    """Check if .claude-wt/worktrees is in .gitignore (local or global)"""
    patterns_to_check = [
        ".claude-wt/worktrees",
        ".claude-wt/worktrees/",
        ".claude-wt/*",
        ".claude-wt/**",
        ".claude-wt",
        ".claude",  # This would also match .claude-wt
    ]

    # Check local .gitignore
    local_gitignore = repo_root / ".gitignore"
    if local_gitignore.exists():
        gitignore_content = local_gitignore.read_text()
        lines = [line.strip() for line in gitignore_content.split("\n")]
        for line in lines:
            if line in patterns_to_check:
                return True

    # Check global .gitignore
    global_gitignore = Path.home() / ".gitignore"
    if global_gitignore.exists():
        gitignore_content = global_gitignore.read_text()
        lines = [line.strip() for line in gitignore_content.split("\n")]
        for line in lines:
            if line in patterns_to_check:
                return True

    # Also check if git is configured to use a different global gitignore
    try:
        import subprocess

        result = subprocess.run(
            ["git", "config", "--global", "core.excludesfile"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            custom_global_gitignore = Path(result.stdout.strip()).expanduser()
            if custom_global_gitignore.exists():
                gitignore_content = custom_global_gitignore.read_text()
                lines = [line.strip() for line in gitignore_content.split("\n")]
                for line in lines:
                    if line in patterns_to_check:
                        return True
    except Exception:
        pass

    return False
