"""Linear issue integration for claude-wt."""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .core import create_worktree_context, get_worktree_base
from .identifier import normalize_linear_id
from .repository import resolve_repo_path
from .tmux_launcher import launch_claude_in_tmux


def handle_linear_issue(
    issue_id: str,
    repo_path: str = ".",
    interactive: bool = True,
    session_name: str | None = None,
):
    """Handle Linear issue worktrees with smart branch/worktree detection.

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
        # Use shared repository resolution (explicit path or current directory)
        repo_root = resolve_repo_path(explicit_path=repo_path if repo_path != "." else None)

        # External worktrees go to sibling directory
        worktree_base = get_worktree_base(repo_root)
        worktree_base.mkdir(parents=True, exist_ok=True)

        # Normalize issue ID using shared function
        issue_prefix = normalize_linear_id(issue_id)

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

        # If session_name provided, use shared tmux/Claude launcher
        if session_name:
            # Use slash command to trigger Linear issue workflow
            initial_prompt = f"/ops-linear-issue {issue_id}"
            launch_claude_in_tmux(session_name, worktree_path, initial_prompt)

        # Successfully completed - worktree path already printed to stdout
        sys.exit(0)

    except subprocess.CalledProcessError as e:
        print(f"Error: {e}", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        raise SystemExit(1)
