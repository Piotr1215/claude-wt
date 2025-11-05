"""Main CLI entry point for claude-wt."""

import subprocess
import sys
from pathlib import Path

from cyclopts import App
from rich.console import Console
from rich.panel import Panel

from .core import check_gitignore
from .github import handle_pr_interactive, handle_pr_noninteractive
from .linear import handle_linear_issue
from .worktree import (
    clean_worktrees,
    create_new_worktree,
    list_worktrees_table,
    switch_worktree,
)

app = App(
    help="Manages isolated git worktrees for parallel Claude Code sessions.\n\n"
         "Use 'claude-wt COMMAND --help' for detailed command options.",
    version_flags=["--version", "-v"],
)
console = Console()


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
    try:
        create_new_worktree(query, branch, name, pull, print_path)
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


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
        clean_worktrees(branch_name, all, scan_dir)
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
        list_worktrees_table(scan_dir)
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
        switch_worktree(scan_dir)
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
def install_completion(shell: str = "zsh"):
    """Install shell completion: install-completion [--shell SHELL]

    Installs shell completion for claude-wt. Currently supports zsh.

    Parameters
    ----------
    shell : str
        Shell to install for (default: zsh)
    """
    if shell != "zsh":
        console.print(f"[red]Error: {shell} completions not yet supported[/red]")
        console.print("[yellow]Currently supported: zsh[/yellow]")
        console.print("[dim]Contributions welcome for bash/fish![/dim]")
        raise SystemExit(1)

    try:
        import importlib.resources as pkg_resources

        # Get completion file content from package
        completion_content = pkg_resources.files("claude_wt").joinpath("../completions/_claude-wt").read_text()

        # Determine installation path
        completion_dir = Path.home() / ".zsh" / "completions"
        completion_file = completion_dir / "_claude-wt"

        # Create directory if needed
        completion_dir.mkdir(parents=True, exist_ok=True)

        # Write completion file
        completion_file.write_text(completion_content)

        console.print(f"[green]✅ Installed zsh completion to:[/green] {completion_file}")
        console.print("\n[yellow]Next steps:[/yellow]")
        console.print("1. Add to your ~/.zshrc (if not already present):")
        console.print("   [cyan]fpath=(~/.zsh/completions $fpath)[/cyan]")
        console.print("   [cyan]autoload -Uz compinit && compinit[/cyan]")
        console.print("\n2. Reload your shell:")
        console.print("   [cyan]exec zsh[/cyan]")
        console.print("\n3. Test it:")
        console.print("   [cyan]claude-wt <TAB>[/cyan]")

    except Exception as e:
        console.print(f"[red]Error installing completion: {e}[/red]")
        console.print("\n[yellow]Manual installation:[/yellow]")
        console.print("See: https://github.com/anthropics/claude-wt/tree/main/completions")
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
    handle_linear_issue(issue_id, repo_path, interactive, session_name)


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
    handle_pr_interactive(pr_number, query)


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
    handle_pr_noninteractive(pr_number, repo_path, session_name)


if __name__ == "__main__":
    app()
