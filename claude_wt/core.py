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

    return (
        branch_name.startswith("claude-wt-")
        or "-worktrees/claude-wt-" in wt_path
    )


def create_worktree_context(
    wt_path: Path, issue_id: str, branch_name: str, repo_root: Path
):
    """Create a CLAUDE.md file specific to this worktree."""
    claude_md = wt_path / "CLAUDE.md"

    content = f"""# Worktree Context

**CRITICAL: You are working in a Git worktree, NOT the main repository!**

## Location Information
- **Current Worktree Path**: `{wt_path}`
- **Main Repository**: `{repo_root}`
- **Issue**: {issue_id}
- **Branch**: `{branch_name}`

## Important Notes
- This is an ISOLATED worktree for issue {issue_id}
- All changes are on branch `{branch_name}`
- You are NOT in the main repository
- Run ALL commands from THIS worktree directory

## Common Commands
```bash
# Check your current location
pwd  # Should show: {wt_path}

# Commit changes
git add .
git commit -m "your message"

# Push to remote
git push origin {branch_name}

# See main repo (DO NOT edit there!)
ls {repo_root}
```

## Remember
You are working in the worktree at:
{wt_path}

This is completely separate from the main repo. All your work here is isolated to the {branch_name} branch.
"""
    claude_md.write_text(content)


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
