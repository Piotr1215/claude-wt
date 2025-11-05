"""GitHub PR integration for claude-wt."""

import json
import re
import subprocess
import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from .core import create_worktree_context, get_worktree_base

console = Console()


def handle_pr_interactive(pr_number: str = "", query: str = ""):
    """Create a worktree from a GitHub PR and launch Claude (interactive).

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
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show-ref",
                    "--verify",
                    f"refs/heads/{pr_branch}",
                ],
                capture_output=True,
            )
            if check_branch.returncode != 0:
                # Local branch doesn't exist, create it tracking origin
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_root),
                        "branch",
                        "--track",
                        pr_branch,
                        f"origin/{pr_branch}",
                    ],
                    check=True,
                    capture_output=True,
                )
        else:
            # Branch doesn't exist in origin (fork PR)
            # Fetch PR and create a local branch
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "fetch",
                    "origin",
                    f"pull/{pr_number}/head:{pr_branch}",
                ],
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
        claude_cmd = [
            "claude",
            "--dangerously-skip-permissions",
            "--add-dir",
            str(repo_root),
            "--",
            initial_query,
        ]
        subprocess.run(claude_cmd, cwd=wt_path)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


def handle_pr_noninteractive(
    pr_number: str,
    repo_path: str = ".",
    session_name: str | None = None,
):
    """Create a worktree from a GitHub PR number non-interactively.

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
        branch_match = re.search(r"(doc|DOC|DEV|dev|ENG|eng)-(\d+)", pr_branch)
        if branch_match:
            linear_issue_id = f"{branch_match.group(1).upper()}-{branch_match.group(2)}"

        # Try PR body (e.g., "Fixes DOC-975" or Linear URL)
        if not linear_issue_id and pr_body:
            body_match = re.search(r"(DOC|DEV|ENG)-\d+", pr_body, re.IGNORECASE)
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
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show-ref",
                    "--verify",
                    f"refs/heads/{pr_branch}",
                ],
                capture_output=True,
            )
            if check_branch.returncode != 0:
                # Local branch doesn't exist, create it tracking origin
                subprocess.run(
                    [
                        "git",
                        "-C",
                        str(repo_root),
                        "branch",
                        "--track",
                        pr_branch,
                        f"origin/{pr_branch}",
                    ],
                    check=True,
                    capture_output=True,
                )
        else:
            # Branch doesn't exist in origin (fork PR)
            # Fetch PR and create a local branch
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "fetch",
                    "origin",
                    f"pull/{pr_number}/head:{pr_branch}",
                ],
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
            claude_cmd = f'claude --dangerously-skip-permissions --add-dir {wt_path} -- "{initial_prompt}"'
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
