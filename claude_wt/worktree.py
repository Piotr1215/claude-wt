"""Worktree operations for claude-wt."""

import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .core import (
    create_worktree_context,
    get_worktree_base,
    install_branch_protection_hook,
    is_claude_wt_worktree,
)
from .tmux import create_tmux_session

console = Console()


def list_all_worktrees(scan_dir: str = "~/dev") -> list[dict]:
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
            # Check if it's actually a git worktree (has .git file pointing to main repo)
            if wt_path.is_dir() and (wt_path / ".git").exists():
                repo_name = wt_base.name.replace("-worktrees", "")
                # Extract session name - remove claude-wt- prefix if present
                session_name = wt_path.name
                if session_name.startswith("claude-wt-"):
                    session_name = session_name.replace("claude-wt-", "", 1)

                all_worktrees.append(
                    {
                        "path": str(wt_path),
                        "repo": repo_name,
                        "session": session_name,
                    }
                )

    return all_worktrees


def select_worktree_fzf(
    worktrees: list[dict], prompt: str = "Select worktree"
) -> dict | None:
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
        "session": parts[2].strip(),
    }


def create_worktree(repo_root: Path, branch_name: str, wt_path: Path) -> None:
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


def create_new_worktree(
    query: str = "",
    branch: str = "",
    name: str = "",
    pull: bool = False,
    print_path: bool = False,
):
    """Create a new worktree in a tmux session."""
    from datetime import datetime

    # Get repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_root = Path(result.stdout.strip())

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
        create_worktree(repo_root, branch_name, wt_path)

    # Create worktree context file
    create_worktree_context(wt_path, f"claude-wt-{suffix}", branch_name, repo_root)

    # Install branch protection hook
    install_branch_protection_hook(wt_path, branch_name)

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

    # Create and switch to tmux session and launch Claude
    session_name = f"wt-{suffix}"
    create_tmux_session(session_name, wt_path, repo_root, query, resume=False)


def list_worktrees_table(scan_dir: str | None = None):
    """List all claude-wt worktrees from all repositories."""
    # Use default if not provided
    if scan_dir is None:
        scan_dir = "~/dev"

    # Get all worktrees
    all_worktrees = list_all_worktrees(scan_dir)

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


def switch_worktree(scan_dir: str | None = None, continue_session: bool = False):
    """Quick switch between worktrees using fzf.

    Parameters
    ----------
    scan_dir : str | None
        Directory to scan for worktrees (default: ~/dev)
    continue_session : bool
        If True, resume Claude conversation with --continue flag
    """
    # Use default if not provided
    if scan_dir is None:
        scan_dir = "~/dev"

    # Get all worktrees
    all_worktrees = list_all_worktrees(scan_dir)

    if not all_worktrees:
        console.print("[yellow]No claude-wt worktrees found.[/yellow]")
        raise SystemExit(1)

    # Select worktree with fzf
    selected_wt = select_worktree_fzf(all_worktrees, "Select worktree to switch to:")

    if not selected_wt:
        console.print("[yellow]No worktree selected[/yellow]")
        raise SystemExit(1)

    wt_path = Path(selected_wt["path"])
    suffix = selected_wt["session"]

    if not wt_path.exists():
        console.print(f"[red]Error: Worktree does not exist: {wt_path}[/red]")
        raise SystemExit(1)

    if continue_session:
        console.print(
            f"[yellow]Switching to session (resuming):[/yellow] [bold]{suffix}[/bold]"
        )
    else:
        console.print(f"[yellow]Switching to session:[/yellow] [bold]{suffix}[/bold]")

    # Get repo root from worktree parent
    repo_root = wt_path.parent.parent / wt_path.parent.name.replace("-worktrees", "")

    # Create and switch to tmux session
    session_name = f"wt-{suffix}"
    create_tmux_session(
        session_name, wt_path, repo_root, query="", resume=continue_session
    )


def clean_worktrees(
    branch_name: str = "",
    all: bool = False,
    scan_dir: str | None = None,
):
    """Delete claude-wt worktrees and branches."""
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
        all_worktrees = list_all_worktrees(scan_dir)

        if not all_worktrees:
            console.print("[yellow]No claude-wt worktrees found.[/yellow]")
            raise SystemExit(1)

        # Select worktree with fzf
        selected_wt = select_worktree_fzf(all_worktrees, "Select worktree to delete:")

        if not selected_wt:
            console.print("[yellow]No worktree selected[/yellow]")
            raise SystemExit(1)

        wt_path = Path(selected_wt["path"])
        session = selected_wt["session"]

        if not wt_path.exists():
            console.print(f"[red]Error: Worktree does not exist: {wt_path}[/red]")
            raise SystemExit(1)

        # Get repo root from worktree
        repo_root = wt_path.parent.parent / wt_path.parent.name.replace(
            "-worktrees", ""
        )

        # Remove worktree
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
            console.print(
                f"[yellow]Could not delete branch (may not exist): {branch_name}[/yellow]"
            )

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
            console.print(f"[yellow]⚠️  Branch {full_branch_name} not found[/yellow]")
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
