"""Tmux session management for claude-wt."""

import os
import subprocess
from pathlib import Path

from rich.console import Console

console = Console()


def create_tmux_session(session_name: str, wt_path: Path) -> bool:
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
