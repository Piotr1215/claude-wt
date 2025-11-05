"""Tmux session management for claude-wt."""

import os
import shutil
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def launch_claude(
    repo_root: Path, wt_path: Path, query: str = "", resume: bool = False
) -> None:
    """Launch Claude Code with appropriate flags.

    Parameters
    ----------
    repo_root : Path
        Repository root directory
    wt_path : Path
        Worktree path
    query : str
        Query to pass to Claude (for new sessions)
    resume : bool
        Whether to resume with --continue flag
    """
    # Find claude executable
    claude_path = shutil.which("claude")
    if not claude_path:
        console.print("[red]Error: 'claude' command not found in PATH[/red]")
        console.print("[yellow]Please install Claude Code CLI first[/yellow]")
        raise SystemExit(1)

    # Build command with --dangerously-skip-permissions for automated workflows
    claude_cmd = [
        claude_path,
        "--dangerously-skip-permissions",
        "--add-dir",
        str(repo_root),
    ]

    if resume:
        claude_cmd.append("--continue")
    elif query:
        claude_cmd.extend(["--", query])

    # Launch Claude
    subprocess.run(claude_cmd, cwd=wt_path)


def create_tmux_session(
    session_name: str,
    wt_path: Path,
    repo_root: Path | None = None,
    query: str = "",
    resume: bool = False,
) -> bool:
    """Create and switch to a tmux session, optionally launching Claude.

    Parameters
    ----------
    session_name : str
        Name of the tmux session
    wt_path : Path
        Worktree path
    repo_root : Path | None
        Repository root (required for launching Claude)
    query : str
        Query to pass to Claude
    resume : bool
        Whether to resume with --continue flag

    Returns
    -------
    bool
        True if successful, False otherwise.
    """
    in_tmux = os.environ.get("TMUX")

    # If not in tmux, just launch Claude directly
    if not in_tmux:
        console.print(f"[cyan]Worktree at:[/cyan] {wt_path}")
        console.print(
            "[yellow]Not running in tmux - launching Claude directly[/yellow]"
        )
        if repo_root:
            launch_claude(repo_root, wt_path, query, resume)
        return False

    try:
        # Check if session already exists
        check_session = subprocess.run(
            ["tmux", "has-session", "-t", session_name], capture_output=True
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

        # Launch Claude in the tmux session
        if repo_root:
            # Send command to tmux session to launch Claude
            claude_path = shutil.which("claude") or "claude"
            claude_cmd_parts = [
                claude_path,
                "--dangerously-skip-permissions",
                "--add-dir",
                str(repo_root),
            ]

            if resume:
                claude_cmd_parts.append("--continue")
            elif query:
                claude_cmd_parts.extend(["--", query])

            # Build the command string for tmux send-keys
            claude_cmd_str = " ".join(
                [
                    f"'{part}'" if " " in str(part) else str(part)
                    for part in claude_cmd_parts
                ]
            )

            # Send the command to the tmux session
            subprocess.run(
                ["tmux", "send-keys", "-t", session_name, claude_cmd_str, "Enter"],
                check=True,
            )
            console.print("[green]Launched Claude in session[/green]")

        return True

    except subprocess.CalledProcessError as e:
        console.print(
            f"[yellow]Warning: Could not create/switch to tmux session: {e}[/yellow]"
        )
        console.print(f"[cyan]Worktree at:[/cyan] {wt_path}")
        # Try to launch Claude directly as fallback
        if repo_root:
            console.print("[yellow]Launching Claude directly...[/yellow]")
            launch_claude(repo_root, wt_path, query, resume)
        return False
