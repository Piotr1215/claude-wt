"""Tmux session management and Claude launcher.

Reusable launcher for all workflows (Linear, PR, custom).
Each function has single responsibility with low cyclomatic complexity.
"""

import subprocess
from pathlib import Path


def launch_claude_in_tmux(
    session_name: str,
    worktree_path: Path,
    initial_prompt: str,
) -> None:
    """Launch Claude in tmux session.

    Creates new session if needed, reuses existing session if present.
    Always sends Claude command to the session.

    Cyclomatic Complexity: 2 (one if check for session existence)
    """
    session_exists = _check_session_exists(session_name)

    if not session_exists:
        _create_tmux_session(session_name, worktree_path)

    _send_claude_command(session_name, worktree_path, initial_prompt)
    _switch_to_session(session_name)


def _check_session_exists(session_name: str) -> bool:
    """Check if tmux session exists.

    Cyclomatic Complexity: 1 (no branching)
    """
    result = subprocess.run(
        ["tmux", "has-session", "-t", session_name], capture_output=True
    )
    return result.returncode == 0


def _create_tmux_session(session_name: str, worktree_path: Path) -> None:
    """Create new tmux session.

    Cyclomatic Complexity: 1 (no branching)
    """
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


def _send_claude_command(
    session_name: str, worktree_path: Path, initial_prompt: str
) -> None:
    """Send Claude command to tmux session.

    Cyclomatic Complexity: 1 (no branching)
    """
    # Build Claude command with KUBECONFIG and explicit path
    claude_launcher = "/home/decoder/dev/dotfiles/scripts/__claude_with_monitor.sh"
    kubeconfig = "/home/decoder/dev/homelab/kubeconfig"

    claude_cmd = (
        f"KUBECONFIG={kubeconfig} {claude_launcher} "
        f'--dangerously-skip-permissions -- "{initial_prompt}"'
    )

    subprocess.run(
        ["tmux", "send-keys", "-t", f"{session_name}:work", claude_cmd, "Enter"]
    )


def _switch_to_session(session_name: str) -> None:
    """Switch to tmux session.

    Cyclomatic Complexity: 1 (no branching)
    """
    subprocess.run(["tmux", "switch-client", "-t", session_name], capture_output=True)
