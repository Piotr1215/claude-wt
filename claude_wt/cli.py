"""Main CLI entry point for claude-wt."""

import subprocess
from pathlib import Path
from typing import Annotated

from cyclopts import App, Parameter
from rich.console import Console

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
    prompt_file: Annotated[str, Parameter(name=["-f", "--prompt-file"])] = "",
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
    prompt_file : str
        Path to file containing prompt (overrides query if provided)
    """
    try:
        # Read prompt from file if provided
        final_query = query
        if prompt_file:
            from pathlib import Path

            prompt_path = Path(prompt_file).expanduser()
            if not prompt_path.exists():
                console.print(f"[red]Error: Prompt file not found: {prompt_file}[/red]")
                raise SystemExit(1)
            final_query = prompt_path.read_text().strip()
            console.print(f"[cyan]Loaded prompt from:[/cyan] {prompt_file}")

        create_new_worktree(final_query, branch, name, pull, print_path)
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
def switch(*, scan_dir: str | None = None, continue_session: bool = False):
    """Switch worktrees: switch [--scan-dir DIR] [--continue]

    Interactively select and switch to a worktree session in tmux.
    Must be run from within a tmux session.

    Parameters
    ----------
    scan_dir : str
        Directory to scan for *-worktrees folders (default: ~/dev)
    continue_session : bool
        Resume previous Claude conversation with --continue flag
    """
    try:
        switch_worktree(scan_dir, continue_session)
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
        completion_content = (
            pkg_resources.files("claude_wt")
            .joinpath("../completions/_claude-wt")
            .read_text()
        )

        # Determine installation path
        completion_dir = Path.home() / ".zsh" / "completions"
        completion_file = completion_dir / "_claude-wt"

        # Create directory if needed
        completion_dir.mkdir(parents=True, exist_ok=True)

        # Write completion file
        completion_file.write_text(completion_content)

        console.print(
            f"[green]✅ Installed zsh completion to:[/green] {completion_file}"
        )
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
        console.print(
            "See: https://github.com/anthropics/claude-wt/tree/main/completions"
        )
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
