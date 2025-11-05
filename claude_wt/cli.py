import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cyclopts import App
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = App(
    help="Manages isolated git worktrees for parallel Claude Code sessions.\n\n"
         "Use 'claude-wt COMMAND --help' for detailed command options.",
    version_flags=["--version", "-v"],
)
console = Console()


def get_worktree_base(repo_root: Path) -> Path:
    """Get the external worktree base directory (sibling to repo)."""
    repo_name = repo_root.name
    return repo_root.parent / f"{repo_name}-worktrees"


def is_claude_wt_worktree(worktree: dict) -> bool:
    """
    Check if a worktree is a claude-wt worktree.

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


# Helper functions to reduce duplication


def _list_all_worktrees(scan_dir: str = "~/dev") -> list[dict]:
    """Scan filesystem for all claude-wt worktrees.

    Returns list of dicts with keys: path, repo, session
    """
    scan_path = Path(scan_dir).expanduser()

    if not scan_path.exists():
        return []

    worktree_dirs = list(scan_path.glob("*-worktrees"))
    all_worktrees = []

    for wt_base in worktree_dirs:
        if not wt_base.is_dir():
            continue

        for wt_path in list(wt_base.iterdir()):
            if wt_path.is_dir() and wt_path.name.startswith("claude-wt-"):
                repo_name = wt_base.name.replace("-worktrees", "")
                all_worktrees.append({
                    "path": str(wt_path),
                    "repo": repo_name,
                    "session": wt_path.name.replace("claude-wt-", "", 1)
                })

    return all_worktrees


def _create_tmux_session(session_name: str, wt_path: Path) -> bool:
    """Create and switch to a tmux session.

    Returns True if successful, False otherwise.
    """
    in_tmux = os.environ.get("TMUX")

    if not in_tmux:
        console.print(f"[cyan]Worktree at:[/cyan] {wt_path}")
        console.print("[yellow]Note: Command works best when run from within tmux[/yellow]")
        return False

    try:
        # Check if session already exists
        check_session = subprocess.run(
            ["tmux", "has-session", "-t", session_name],
            capture_output=True
        )

        if check_session.returncode != 0:
            # Create new tmux session
            subprocess.run(
                [
                    "tmux",
                    "new-session",
                    "-d",
                    "-s",
                    session_name,
                    "-c",
                    str(wt_path),
                ],
                check=True,
            )
            console.print(f"[cyan]Created tmux session:[/cyan] {session_name}")
            console.print(f"[dim]Session working directory:[/dim] {wt_path}")

        # Switch to the session
        subprocess.run(["tmux", "switch-client", "-t", session_name])
        console.print(f"[green]Switched to tmux session:[/green] {session_name}")
        return True

    except subprocess.CalledProcessError as e:
        console.print(f"[yellow]Warning: Could not create/switch to tmux session: {e}[/yellow]")
        console.print(f"[cyan]Worktree at:[/cyan] {wt_path}")
        return False


def _create_worktree(repo_root: Path, branch_name: str, wt_path: Path) -> None:
    """Create a git worktree."""
    subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "worktree",
            "add",
            "--quiet",
            str(wt_path),
            branch_name,
        ],
        check=True,
    )


def _select_worktree_fzf(worktrees: list[dict], prompt: str = "Select worktree") -> dict | None:
    """Show fzf picker for worktrees.

    Returns selected worktree dict or None if cancelled.
    """
    if not worktrees:
        return None

    # Create fzf input
    fzf_input = []
    for wt in sorted(worktrees, key=lambda x: (x["repo"], x["session"])):
        exists = "[OK]" if Path(wt["path"]).exists() else "[X]"
        fzf_input.append(f"{exists} {wt['repo']:<20} {wt['session']:<30} {wt['path']}")

    # Use fzf to select
    try:
        result = subprocess.run(
            [
                "fzf",
                "--height",
                "40%",
                "--reverse",
                "--header",
                prompt,
                "--prompt",
                "> ",
            ],
            input="\n".join(fzf_input),
            capture_output=True,
            text=True,
            check=True,
        )
        selected = result.stdout.strip()
    except subprocess.CalledProcessError:
        return None

    # Parse selection
    parts = selected.split()
    if len(parts) < 4:
        return None

    return {
        "path": parts[3].strip(),
        "repo": parts[1].strip(),
        "session": parts[2].strip()
    }


@app.command
def new(
    query: str = "",
    branch: str = "",
    name: str = "",
    pull: bool = False,
    print_path: bool = False,
):
    """Create new worktree: new [name] [--branch BRANCH] [--pull]

    Creates an isolated git worktree in a sibling directory and launches
    a tmux session for working on a specific feature or task.

    Parameters
    ----------
    query : str
        Optional initial query/task description
    branch : str
        Source branch to create worktree from (default: current branch)
    name : str
        Name suffix for the worktree branch (default: timestamp)
    pull : bool
        Pull latest changes before creating worktree (default: False)
    print_path : bool
        Print worktree path to stdout only (for scripting)
    """
    # Get repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_root = Path(result.stdout.strip())

    # Worktrees are now in sibling directory, so gitignore is not strictly required
    # But we still check and warn for cleanliness
    # (This is now optional since worktrees are external to the repo)

    # Get source branch (default to current branch)
    if branch:
        source_branch = branch
    else:
        result = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        source_branch = result.stdout.strip()

    # Optionally sync with origin (skip by default for speed)
    if pull:
        console.print("[cyan]Fetching latest changes...[/cyan]")
        subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True)
        subprocess.run(
            ["git", "-C", str(repo_root), "switch", "--quiet", source_branch],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_root), "pull", "--ff-only", "--quiet"], check=True
        )
        console.print("[green]✓ Synced with origin[/green]")
    else:
        # Just ensure we're on the source branch (fast)
        subprocess.run(
            ["git", "-C", str(repo_root), "switch", "--quiet", source_branch],
            check=True,
        )

    # Generate worktree branch name
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    suffix = name or timestamp
    branch_name = f"claude-wt-{suffix}"

    # Create branch if needed
    try:
        subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{branch_name}",
            ],
            check=True,
        )
    except subprocess.CalledProcessError:
        subprocess.run(
            ["git", "-C", str(repo_root), "branch", branch_name, source_branch],
            check=True,
        )

    # Setup external worktree path in sibling directory
    worktree_base = get_worktree_base(repo_root)
    worktree_base.mkdir(parents=True, exist_ok=True)
    wt_path = worktree_base / branch_name

    # Create worktree if needed
    if not wt_path.exists():
        _create_worktree(repo_root, branch_name, wt_path)

    # Create worktree context file
    create_worktree_context(wt_path, f"claude-wt-{suffix}", branch_name, repo_root)

    # If print_path is set, just output the path for shell integration
    if print_path:
        print(str(wt_path))
        return

    # Print helpful info
    panel_content = f"""[dim]Source branch:[/dim] [cyan]{source_branch}[/cyan]

[green]Switch to session:[/green] [bold]claude-wt switch[/bold]
[blue]Delete this session:[/blue] [bold]claude-wt clean[/bold]
[red]Delete all sessions:[/red] [bold]claude-wt clean --all[/bold]"""

    console.print(
        Panel(
            panel_content,
            title="[bold cyan]Session Created[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )

    # Create and switch to tmux session
    session_name = f"wt-{suffix}"
    _create_tmux_session(session_name, wt_path)


@app.command
def clean(
    branch_name: str = "",
    *,
    all: bool = False,
    scan_dir: str | None = None,
):
    """Clean worktrees: clean [branch-name] [--all] [--scan-dir DIR]

    Removes worktrees and optionally their branches. Interactive fzf picker
    if no branch specified. Works with both regular and issue-based worktrees.

    Parameters
    ----------
    branch_name : str
        Specific branch to clean (optional - shows fzf if not provided)
    all : bool
        Clean all claude-wt sessions in current repository
    scan_dir : str
        Directory to scan for worktrees (default: ~/dev)
    """
    try:
        # Use default scan dir if not provided
        if scan_dir is None:
            scan_dir = "~/dev"

        if branch_name and all:
            console.print(
                "[red]Error: Cannot specify both branch name and --all flag[/red]"
            )
            raise SystemExit(1)

        # If no branch_name and not --all, show fzf dialog
        if not branch_name and not all:
            # Get all worktrees
            all_worktrees = _list_all_worktrees(scan_dir)

            if not all_worktrees:
                console.print("[yellow]No claude-wt worktrees found.[/yellow]")
                raise SystemExit(1)

            # Select worktree with fzf
            selected_wt = _select_worktree_fzf(all_worktrees, "Select worktree to delete:")

            if not selected_wt:
                console.print("[yellow]No worktree selected[/yellow]")
                raise SystemExit(1)

            wt_path = Path(selected_wt["path"])
            session = selected_wt["session"]

            if not wt_path.exists():
                console.print(f"[red]Error: Worktree does not exist: {wt_path}[/red]")
                raise SystemExit(1)

            # Get repo root from worktree
            repo_root = wt_path.parent.parent / wt_path.parent.name.replace("-worktrees", "")

            # Remove worktree
            subprocess.run(
                ["git", "-C", str(repo_root), "worktree", "remove", "--force", str(wt_path)],
                check=True,
            )
            console.print(f"[green]Removed worktree:[/green] {wt_path}")

            # Try to delete branch
            branch_name = f"claude-wt-{session}"
            try:
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "-D", branch_name],
                    check=True,
                    capture_output=True,
                )
                console.print(f"[green]Deleted branch:[/green] {branch_name}")
            except subprocess.CalledProcessError:
                # Branch might not exist or have a different name
                console.print(f"[yellow]Could not delete branch (may not exist): {branch_name}[/yellow]")

            return

        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
        worktree_base = get_worktree_base(repo_root)

        if branch_name:
            # Clean specific branch
            full_branch_name = f"claude-wt-{branch_name}"
            wt_path = worktree_base / full_branch_name

            # Remove worktree
            if wt_path.exists():
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_root),
                        "worktree",
                        "remove",
                        "--force",
                        str(wt_path),
                    ],
                    check=True,
                )
                console.print(f"[green]✅ Removed worktree:[/green] {wt_path}")

            # Delete branch
            try:
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "-D", full_branch_name],
                    check=True,
                )
                console.print(f"[green]✅ Deleted branch:[/green] {full_branch_name}")
            except subprocess.CalledProcessError:
                console.print(
                    f"[yellow]⚠️  Branch {full_branch_name} not found[/yellow]"
                )
        else:
            # Clean all claude-wt branches/worktrees
            with console.status("[bold cyan]Cleaning all claude-wt sessions..."):
                # Get all worktrees from git and remove claude-wt ones
                console.print("[cyan]Removing claude-wt worktrees...[/cyan]")
                try:
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_root),
                            "worktree",
                            "list",
                            "--porcelain",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )

                    # Parse worktree list to find claude-wt worktrees
                    worktrees = []
                    current_wt = {}
                    for line in result.stdout.split("\n"):
                        if line.startswith("worktree "):
                            if current_wt:
                                worktrees.append(current_wt)
                            current_wt = {"path": line[9:]}
                        elif line.startswith("branch "):
                            current_wt["branch"] = line[7:]
                    if current_wt:
                        worktrees.append(current_wt)

                    # Remove worktrees - both claude-wt-* branches and those in .claude-wt/worktrees
                    for wt in worktrees:
                        wt_path = wt.get("path", "")
                        branch_name = wt.get("branch", "")

                        # Check if this is a claude-wt worktree
                        if is_claude_wt_worktree(wt):
                            try:
                                subprocess.run(
                                    [
                                        "git",
                                        "-C",
                                        str(repo_root),
                                        "worktree",
                                        "remove",
                                        "--force",
                                        wt_path,
                                    ],
                                    check=True,
                                )
                                console.print(
                                    f"  [green]✅ Removed worktree: {branch_name or wt_path}[/green]"
                                )
                            except subprocess.CalledProcessError:
                                console.print(
                                    f"  [red]❌ Failed to remove worktree: {branch_name or wt_path}[/red]"
                                )
                                # Try to prune if removal failed
                                try:
                                    subprocess.run(
                                        [
                                            "git",
                                            "-C",
                                            str(repo_root),
                                            "worktree",
                                            "prune",
                                        ],
                                        check=True,
                                    )
                                except Exception:
                                    pass
                except subprocess.CalledProcessError:
                    console.print("  [yellow]No worktrees found[/yellow]")

                # Delete branches
                console.print("[cyan]Deleting claude-wt branches...[/cyan]")
                try:
                    result = subprocess.run(
                        [
                            "git",
                            "-C",
                            str(repo_root),
                            "branch",
                            "--list",
                            "claude-wt-*",
                        ],
                        capture_output=True,
                        text=True,
                        check=True,
                    )
                    branches = [
                        b.strip().lstrip("* ").lstrip("+ ")
                        for b in result.stdout.split("\n")
                        if b.strip()
                    ]

                    for branch in branches:
                        if branch:
                            try:
                                subprocess.run(
                                    [
                                        "git",
                                        "-C",
                                        str(repo_root),
                                        "branch",
                                        "-D",
                                        branch,
                                    ],
                                    check=True,
                                )
                                console.print(
                                    f"  [green]✅ Deleted branch {branch}[/green]"
                                )
                            except subprocess.CalledProcessError:
                                console.print(
                                    f"  [red]❌ Failed to delete branch {branch}[/red]"
                                )
                except subprocess.CalledProcessError:
                    console.print("  [yellow]No claude-wt-* branches found[/yellow]")

            console.print("[green bold]🧹 Cleanup complete![/green bold]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command(name="list")
def list_worktrees(*, scan_dir: str | None = None):
    """List worktrees: list [--scan-dir DIR]

    Scans for worktree directories and displays them in a table with
    status, repository, session name, and full path.

    Parameters
    ----------
    scan_dir : str
        Directory to scan for *-worktrees folders (default: ~/dev)
    """
    try:
        # Use default if not provided
        if scan_dir is None:
            scan_dir = "~/dev"

        # Get all worktrees
        all_worktrees = _list_all_worktrees(scan_dir)

        if not all_worktrees:
            console.print("[yellow]No claude-wt worktrees found.[/yellow]")
            return

        # Create table
        table = Table(title="[bold cyan]All Claude-wt worktrees[/bold cyan]")
        table.add_column("Status", style="green", justify="center")
        table.add_column("Repository", style="magenta", min_width=15)
        table.add_column("Session", style="cyan", min_width=15)
        table.add_column("Path", style="dim", overflow="fold")

        for wt in sorted(all_worktrees, key=lambda x: (x["repo"], x["session"])):
            # Check if worktree path still exists
            status = "[green]OK[/green]" if Path(wt["path"]).exists() else "[red]X[/red]"
            table.add_row(status, wt["repo"], wt["session"], wt["path"])

        console.print(table)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        import traceback
        console.print(f"[red]Unexpected error: {e}[/red]")
        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        raise SystemExit(1)


@app.command
def switch(*, scan_dir: str | None = None):
    """Switch worktrees: switch [--scan-dir DIR]

    Interactively select and switch to a worktree session in tmux.
    Must be run from within a tmux session.

    Parameters
    ----------
    scan_dir : str
        Directory to scan for *-worktrees folders (default: ~/dev)
    """
    try:
        # Use default if not provided
        if scan_dir is None:
            scan_dir = "~/dev"

        # Get all worktrees
        all_worktrees = _list_all_worktrees(scan_dir)

        if not all_worktrees:
            console.print("[yellow]No claude-wt worktrees found.[/yellow]")
            raise SystemExit(1)

        # Select worktree with fzf
        selected_wt = _select_worktree_fzf(all_worktrees, "Select worktree to switch to:")

        if not selected_wt:
            console.print("[yellow]No worktree selected[/yellow]")
            raise SystemExit(1)

        wt_path = Path(selected_wt["path"])
        suffix = selected_wt["session"]

        if not wt_path.exists():
            console.print(f"[red]Error: Worktree does not exist: {wt_path}[/red]")
            raise SystemExit(1)

        console.print(
            f"[yellow]Switching to session:[/yellow] [bold]{suffix}[/bold]"
        )

        # Create and switch to tmux session
        session_name = f"wt-{suffix}"
        _create_tmux_session(session_name, wt_path)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def status():
    """Show status: status

    Displays information about the current directory: whether you're in
    a worktree, the branch name, and available commands.
    """
    try:
        cwd = Path.cwd()

        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.returncode != 0:
            console.print("[yellow]Not in a git repository[/yellow]")
            raise SystemExit(1)

        repo_root = Path(result.stdout.strip())

        # Get current branch
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            capture_output=True,
            text=True,
            check=True,
        )
        current_branch = result.stdout.strip()

        # Check if we're in a worktree
        result = subprocess.run(
            ["git", "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse worktrees to find if current directory is a worktree
        in_worktree = False
        worktree_branch = None
        main_repo_path = None

        current_wt = {}
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current_wt:
                    wt_path = Path(current_wt.get("path", ""))
                    if wt_path == repo_root:
                        # This is the main repo
                        main_repo_path = wt_path
                    elif wt_path == cwd or cwd.is_relative_to(wt_path):
                        in_worktree = True
                        worktree_branch = current_wt.get("branch", "")
                current_wt = {"path": line[9:]}
            elif line.startswith("branch "):
                current_wt["branch"] = line[7:]

        # Check last entry
        if current_wt:
            wt_path = Path(current_wt.get("path", ""))
            if wt_path == repo_root:
                main_repo_path = wt_path
            elif wt_path == cwd or cwd.is_relative_to(wt_path):
                in_worktree = True
                worktree_branch = current_wt.get("branch", "")

        # Build status panel
        is_claude_wt = current_branch.startswith("claude-wt-")

        if is_claude_wt and in_worktree:
            session_name = current_branch.replace("claude-wt-", "")
            status_icon = "🟢"
            status_text = f"[green]Active Claude worktree session[/green]"
            panel_content = f"""{status_text}

[dim]Session:[/dim] [cyan]{session_name}[/cyan]
[dim]Branch:[/dim] [cyan]{current_branch}[/cyan]
[dim]Location:[/dim] {cwd}
[dim]Main repo:[/dim] {repo_root}

[yellow]Commands:[/yellow]
  • [bold]claude-wt switch[/bold] - Switch to another session
  • [bold]claude-wt list[/bold] - List all sessions
  • [bold]claude-wt clean {session_name}[/bold] - Clean up this session"""
        elif in_worktree:
            status_icon = "📂"
            status_text = "[yellow]In a worktree (not claude-wt)[/yellow]"
            panel_content = f"""{status_text}

[dim]Branch:[/dim] {current_branch}
[dim]Location:[/dim] {cwd}
[dim]Main repo:[/dim] {repo_root}"""
        else:
            status_icon = "📦"
            status_text = "[blue]In main repository[/blue]"
            panel_content = f"""{status_text}

[dim]Branch:[/dim] {current_branch}
[dim]Location:[/dim] {repo_root}

[yellow]Commands:[/yellow]
  • [bold]claude-wt new "task description"[/bold] - Create new session
  • [bold]claude-wt switch[/bold] - Switch to existing session
  • [bold]claude-wt list[/bold] - List all sessions"""

        console.print(
            Panel(
                panel_content,
                title=f"{status_icon} [bold]Claude-wt Status[/bold]",
                border_style="cyan",
                expand=False,
            )
        )

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def init():
    """Initialize repo: init

    Adds .claude-wt/worktrees to .gitignore. NOTE: With external worktrees
    in sibling directories, this is mostly optional but kept for backwards
    compatibility.
    """
    try:
        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())

        # Check if already in gitignore
        if check_gitignore(repo_root):
            console.print(
                "[green]✅ .claude-wt/worktrees is already in .gitignore[/green]"
            )
            return

        gitignore_path = repo_root / ".gitignore"

        # Read existing content
        if gitignore_path.exists():
            existing_content = gitignore_path.read_text()
            # Add a newline if the file doesn't end with one
            if existing_content and not existing_content.endswith("\n"):
                existing_content += "\n"
        else:
            existing_content = ""

        # Add the ignore entry
        new_content = (
            existing_content + "\n# Claude worktree management\n.claude-wt/worktrees\n"
        )

        # Write back to file
        gitignore_path.write_text(new_content)

        console.print("[green]✅ Added .claude-wt/worktrees to .gitignore[/green]")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)






@app.command
def linear_issue(
    issue_id: str,
    repo_path: str = ".",
    interactive: bool = True,
    session_name: str | None = None,
):
    """Linear issue: linear-issue ISSUE-ID [--repo-path PATH] [--no-interactive] [--session-name NAME]

    Handles Linear issue worktrees with smart branch/worktree detection.
    Primary command used by taskwarrior hooks for +wt tasks.

    Workflow: (1) Checks for existing branches/worktrees, (2) Shows interactive
    picker if enabled, (3) Creates worktree in sibling directory, (4) Optionally
    launches tmux session with Claude.

    Parameters
    ----------
    issue_id : str
        Linear issue ID (e.g., DOC-975, ENG-123)
    repo_path : str
        Repository path (default: current directory)
    interactive : bool
        Enable interactive prompts with zenity (default: True)
    session_name : str
        Optional tmux session name to create and launch Claude
    """
    try:
        # Get repo root
        if repo_path == ".":
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
        else:
            repo_root = Path(repo_path).resolve()

        # External worktrees go to sibling directory
        worktree_base = get_worktree_base(repo_root)
        worktree_base.mkdir(parents=True, exist_ok=True)

        # Normalize issue ID
        issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
        issue_prefix = f"doc-{issue_prefix}"  # Ensure it starts with doc-

        # Get existing branches for this issue
        result = subprocess.run(
            ["git", "-C", str(repo_root), "branch", "-a"],
            capture_output=True,
            text=True,
            check=True,
        )

        existing_branches = []
        for line in result.stdout.split("\n"):
            branch = line.strip().lstrip("* ").lstrip("+ ").strip()
            if branch and not branch.startswith("remotes/"):
                if "/" in branch and branch.startswith(issue_prefix + "/"):
                    existing_branches.append(branch)

        # Get existing worktrees for this issue
        existing_worktrees = []
        if worktree_base.exists():
            for entry in worktree_base.iterdir():
                if entry.is_dir() and entry.name.startswith(issue_prefix + "-"):
                    existing_worktrees.append(entry.name)

        worktree_path = None
        branch_name = None

        # Interactive selection
        if interactive and (existing_branches or existing_worktrees):
            # Use zenity for GUI selection
            command = [
                "zenity",
                "--list",
                f"--title=Branches/Worktrees for {issue_id}",
                "--text=Select an existing branch/worktree or create new:",
                "--column=Option",
                "--width=500",
                "--height=400",
            ]

            # Add existing worktrees
            for wt in existing_worktrees:
                command.append(f"[worktree exists] {wt}")

            # Add existing branches without worktrees
            for branch in existing_branches:
                wt_name = branch.replace("/", "-")
                if wt_name not in existing_worktrees:
                    command.append(f"[create worktree] {branch}")

            command.append("Create new branch")

            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, check=True
                )
                selection = result.stdout.strip()

                if selection.startswith("[worktree exists]"):
                    # Use existing worktree
                    wt_name = selection.replace("[worktree exists] ", "").strip()
                    worktree_path = worktree_base / wt_name
                    # Extract branch name from worktree name
                    branch_name = wt_name.replace(issue_prefix + "-", "")
                    branch_name = f"{issue_prefix}/{branch_name}"

                elif selection.startswith("[create worktree]"):
                    # Create worktree for existing branch
                    branch_name = selection.replace("[create worktree] ", "").strip()

                elif selection == "Create new branch":
                    # Prompt for new branch name
                    branch_name = None

                else:
                    # User cancelled
                    raise SystemExit(1)

            except subprocess.CalledProcessError:
                # User cancelled
                raise SystemExit(1)

        # If we need a new branch name
        if not branch_name and interactive:
            # Prompt for branch name using zenity
            try:
                result = subprocess.run(
                    [
                        "zenity",
                        "--entry",
                        "--title=Create New Branch",
                        f"--text=Creating worktree for issue {issue_id}\\nEnter branch name suffix:",
                        "--width=400",
                    ],
                    capture_output=True,
                    text=True,
                    check=True,
                )

                branch_suffix = result.stdout.strip()
                if not branch_suffix:
                    raise SystemExit(1)

                branch_name = f"{issue_prefix}/{branch_suffix}"

            except subprocess.CalledProcessError:
                # User cancelled
                raise SystemExit(1)

        elif not branch_name:
            # Non-interactive: create with timestamp
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            branch_name = f"{issue_prefix}/{timestamp}"

        # Create worktree if needed
        if not worktree_path:
            # Ensure we're on main and up to date
            subprocess.run(
                ["git", "-C", str(repo_root), "fetch", "origin"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_root), "checkout", "main"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "-C", str(repo_root), "pull", "--ff-only"],
                check=True,
                capture_output=True,
            )

            # Check if branch exists
            result = subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show-ref",
                    "--verify",
                    f"refs/heads/{branch_name}",
                ],
                capture_output=True,
            )

            if result.returncode != 0:
                # Create new branch
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", branch_name, "main"],
                    check=True,
                )

            # Create worktree
            wt_name = branch_name.replace("/", "-")
            worktree_path = worktree_base / wt_name

            if not worktree_path.exists():
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_root),
                        "worktree",
                        "add",
                        str(worktree_path),
                        branch_name,
                    ],
                    check=True,
                    capture_output=True,
                )

        # Create worktree-specific CLAUDE.md
        create_worktree_context(worktree_path, issue_id, branch_name, repo_root)

        # Output path for automation (to stdout)
        print(str(worktree_path))

        # If session_name provided, create tmux session and launch Claude
        if session_name:
            # Check if session exists
            check_session = subprocess.run(
                ["tmux", "has-session", "-t", session_name], capture_output=True
            )

            if check_session.returncode != 0:
                # Create new tmux session with single pane
                subprocess.run(
                    [
                        "tmux",
                        "new-session",
                        "-d",
                        "-s",
                        session_name,
                        "-c",
                        str(worktree_path),
                        "-n",
                        "work",
                    ]
                )

                # Launch Claude with issue context
                initial_prompt = f"Working on issue {issue_id} in worktree at {worktree_path}"
                claude_cmd = f'claude --add-dir {worktree_path} -- "{initial_prompt}"'
                subprocess.run(
                    [
                        "tmux",
                        "send-keys",
                        "-t",
                        f"{session_name}:work",
                        claude_cmd,
                        "Enter",
                    ]
                )

                # Switch to session
                subprocess.run(
                    ["tmux", "switch-client", "-t", session_name], capture_output=True
                )

        # Successfully completed - worktree path already printed to stdout
        sys.exit(0)

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise SystemExit(1)




@app.command
def from_pr(pr_number: str = "", query: str = ""):
    """GitHub PR (interactive): from-pr [PR-NUMBER] [query]

    Fetches PR branch, creates worktree, and launches Claude with PR context.
    Requires 'gh' CLI to be installed and authenticated.

    Parameters
    ----------
    pr_number : str
        GitHub PR number (optional - shows fzf picker if not provided)
    query : str
        Optional additional context/query to send to Claude
    """
    try:
        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())

        # If no PR number provided, prompt for it
        if not pr_number:
            console.print("[cyan]Fetching open PRs...[/cyan]")

            # List open PRs
            result = subprocess.run(
                ["gh", "pr", "list", "--json", "number,title,author,headRefName"],
                capture_output=True,
                text=True,
                check=True,
                cwd=repo_root,
            )

            prs = json.loads(result.stdout)
            if not prs:
                console.print("[yellow]No open PRs found[/yellow]")
                raise SystemExit(1)

            # Use fzf to select a PR
            fzf_input = "\n".join(
                [
                    f"#{pr['number']}: {pr['title']} (by {pr['author']['login']})"
                    for pr in prs
                ]
            )

            try:
                result = subprocess.run(
                    ["fzf", "--height", "40%", "--reverse"],
                    input=fzf_input,
                    capture_output=True,
                    text=True,
                    check=True,
                )
                selected = result.stdout.strip()
                pr_number = selected.split(":")[0].lstrip("#")
            except subprocess.CalledProcessError:
                console.print("[yellow]No PR selected[/yellow]")
                raise SystemExit(1)

        # Get PR details using gh CLI
        pr_info = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "headRefName,title,number,body"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )

        pr_data = json.loads(pr_info.stdout)
        pr_branch = pr_data["headRefName"]
        pr_title = pr_data.get("title", "")
        pr_body = pr_data.get("body", "")

        # Fetch the PR branch from origin
        fetch_result = subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "origin", pr_branch],
            capture_output=True,
        )

        if fetch_result.returncode == 0:
            # Branch exists in origin (same-repo PR)
            # Create local branch tracking origin/branch if it doesn't exist
            check_branch = subprocess.run(
                ["git", "-C", str(repo_root), "show-ref", "--verify", f"refs/heads/{pr_branch}"],
                capture_output=True,
            )
            if check_branch.returncode != 0:
                # Local branch doesn't exist, create it tracking origin
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "--track", pr_branch, f"origin/{pr_branch}"],
                    check=True,
                    capture_output=True,
                )
        else:
            # Branch doesn't exist in origin (fork PR)
            # Fetch PR and create a local branch
            subprocess.run(
                ["git", "-C", str(repo_root), "fetch", "origin", f"pull/{pr_number}/head:{pr_branch}"],
                check=True,
                capture_output=True,
            )

        # Setup external worktree path in sibling directory
        worktree_base = get_worktree_base(repo_root)
        worktree_base.mkdir(parents=True, exist_ok=True)
        wt_name = f"pr-{pr_number}-{pr_branch.replace('/', '-')}"
        wt_path = worktree_base / wt_name

        # Create worktree if it doesn't exist - always use local branch name
        if not wt_path.exists():
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    "--quiet",
                    str(wt_path),
                    pr_branch,
                ],
                check=True,
                capture_output=True,
            )

        # Create worktree-specific CLAUDE.md
        create_worktree_context(wt_path, f"PR #{pr_number}", pr_branch, repo_root)

        # Print helpful info
        panel_content = f"""[dim]PR:[/dim] [cyan]#{pr_number}[/cyan] - {pr_title}
[dim]Branch:[/dim] [cyan]{pr_branch}[/cyan]
[dim]Worktree:[/dim] [cyan]{wt_path.name}[/cyan]

[green]🟢 Resume this session:[/green] [bold]claude-wt resume-pr {pr_number}[/bold]
[blue]🧹 Delete this session:[/blue] [bold]claude-wt clean-pr {pr_number}[/bold]"""

        console.print(
            Panel(
                panel_content,
                title="[bold cyan]Session Created from GitHub PR[/bold cyan]",
                border_style="cyan",
                expand=False,
            )
        )

        # Prepare initial query with PR context
        initial_query = f"I'm reviewing PR #{pr_number}: {pr_title}\n\n"
        if pr_body:
            initial_query += f"PR Description:\n{pr_body}\n\n"
        initial_query += f"Please review this PR using /ops-pr-review {pr_number}"

        if query:
            initial_query = f"{initial_query}\n\nAdditional context: {query}"

        # Launch Claude with PR context
        claude_cmd = ["claude", "--add-dir", str(repo_root), "--", initial_query]
        subprocess.run(claude_cmd, cwd=wt_path)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def from_pr_noninteractive(
    pr_number: str,
    repo_path: str = ".",
    session_name: str | None = None,
):
    """GitHub PR (non-interactive): from-pr-noninteractive PR-NUMBER [--repo-path PATH] [--session-name NAME]

    Used by taskwarrior hooks for automated PR worktree creation.
    Outputs worktree path to stdout for scripting.

    Parameters
    ----------
    pr_number : str
        GitHub PR number (e.g., 1234)
    repo_path : str
        Repository path (default: current directory)
    session_name : str
        Optional tmux session name to create and launch Claude
    """
    try:
        # Get repo root
        if repo_path == ".":
            result = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                capture_output=True,
                text=True,
                check=True,
            )
            repo_root = Path(result.stdout.strip())
        else:
            repo_root = Path(repo_path).resolve()

        # Get PR details using gh CLI
        pr_info = subprocess.run(
            ["gh", "pr", "view", pr_number, "--json", "headRefName,title,number,body"],
            capture_output=True,
            text=True,
            check=True,
            cwd=repo_root,
        )

        pr_data = json.loads(pr_info.stdout)
        pr_branch = pr_data["headRefName"]
        pr_body = pr_data.get("body", "")

        # Extract Linear issue ID from branch name or PR body
        linear_issue_id = None

        # Try branch name first (e.g., doc-975-feature, DOC-975-feature)
        branch_match = re.search(r'(doc|DOC|DEV|dev|ENG|eng)-(\d+)', pr_branch)
        if branch_match:
            linear_issue_id = f"{branch_match.group(1).upper()}-{branch_match.group(2)}"

        # Try PR body (e.g., "Fixes DOC-975" or Linear URL)
        if not linear_issue_id and pr_body:
            body_match = re.search(r'(DOC|DEV|ENG)-\d+', pr_body, re.IGNORECASE)
            if body_match:
                linear_issue_id = body_match.group(0).upper()

        # Determine skill to activate based on repo name
        repo_name = repo_root.name.lower()
        skill_instruction = ""
        if "vcluster-docs" in repo_name:
            skill_instruction = "Activate the vcluster-docs-writer skill to get context-aware assistance."
        elif "platform-docs" in repo_name:
            skill_instruction = "Activate appropriate documentation skills."

        # Setup external worktree path in sibling directory
        worktree_base = get_worktree_base(repo_root)
        worktree_base.mkdir(parents=True, exist_ok=True)
        wt_name = f"pr-{pr_number}-{pr_branch.replace('/', '-')}"
        wt_path = worktree_base / wt_name

        # Try to fetch the PR branch from origin
        fetch_result = subprocess.run(
            ["git", "-C", str(repo_root), "fetch", "origin", pr_branch],
            capture_output=True,
        )

        if fetch_result.returncode == 0:
            # Branch exists in origin (same-repo PR)
            # Create local branch tracking origin/branch if it doesn't exist
            check_branch = subprocess.run(
                ["git", "-C", str(repo_root), "show-ref", "--verify", f"refs/heads/{pr_branch}"],
                capture_output=True,
            )
            if check_branch.returncode != 0:
                # Local branch doesn't exist, create it tracking origin
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "--track", pr_branch, f"origin/{pr_branch}"],
                    check=True,
                    capture_output=True,
                )
        else:
            # Branch doesn't exist in origin (fork PR)
            # Fetch PR and create a local branch
            subprocess.run(
                ["git", "-C", str(repo_root), "fetch", "origin", f"pull/{pr_number}/head:{pr_branch}"],
                check=True,
                capture_output=True,
            )

        # Create worktree if it doesn't exist - always use local branch name
        if not wt_path.exists():
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "worktree",
                    "add",
                    "--quiet",
                    str(wt_path),
                    pr_branch,
                ],
                check=True,
                capture_output=True,
            )
            print(f"Created worktree at {wt_path}", file=sys.stderr)
        else:
            # Worktree exists, pull latest
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(wt_path),
                    "pull",
                ],
                check=True,
                capture_output=True,
            )
            print(
                f"Worktree already exists at {wt_path}, pulled latest changes",
                file=sys.stderr,
            )

        # Create worktree-specific CLAUDE.md
        create_worktree_context(wt_path, f"PR #{pr_number}", pr_branch, repo_root)

        # Output the worktree path for the hook to use
        print(str(wt_path))

        # If session_name provided, create tmux session and launch Claude
        if session_name:
            # DEBUG: Log session creation
            with open("/tmp/claude-wt-session-debug.log", "a") as f:
                f.write("\n=== from_pr_noninteractive SESSION CREATION ===\n")
                f.write(f"session_name parameter: '{session_name}'\n")
                f.write(f"worktree_path: {wt_path}\n")
                f.write(f"pr_number: {pr_number}\n")

            # Check if session exists
            check_session = subprocess.run(
                ["tmux", "has-session", "-t", session_name], capture_output=True
            )

            if check_session.returncode != 0:
                # DEBUG: Log actual creation
                with open("/tmp/claude-wt-session-debug.log", "a") as f:
                    f.write(f"Creating NEW tmux session: '{session_name}'\n")

                # Create new tmux session
                subprocess.run(
                    [
                        "tmux",
                        "new-session",
                        "-d",
                        "-s",
                        session_name,
                        "-c",
                        str(wt_path),
                        "-n",
                        "work",
                    ]
                )
            else:
                with open("/tmp/claude-wt-session-debug.log", "a") as f:
                    f.write(f"Session '{session_name}' ALREADY EXISTS\n")

            # Launch Claude with PR review command (ALWAYS - new or existing session)
            # Build initial prompt with multiple commands
            prompt_parts = []

            # Add Linear issue command if found
            if linear_issue_id:
                prompt_parts.append(f"/ops-linear-issue {linear_issue_id}")

            # Add skill activation instruction if applicable
            if skill_instruction:
                prompt_parts.append(skill_instruction)

            # Add PR review command
            prompt_parts.append(f"/ops-pr-review {pr_number}")

            # Combine with double newlines
            initial_prompt = "\n\n".join(prompt_parts)

            # Launch Claude in the worktree with multi-command prompt
            claude_cmd = f'claude --add-dir {wt_path} -- "{initial_prompt}"'
            subprocess.run(
                [
                    "tmux",
                    "send-keys",
                    "-t",
                    f"{session_name}:work",
                    claude_cmd,
                    "Enter",
                ]
            )

            # Switch to session
            subprocess.run(
                ["tmux", "switch-client", "-t", session_name], capture_output=True
            )

        # Successfully completed - worktree path already printed to stdout
        sys.exit(0)

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
