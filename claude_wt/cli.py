import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cyclopts import App
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

app = App(help="Claude worktree management CLI")
console = Console()


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
    except:
        pass
    
    return False


@app.command
def new(
    query: str = "",
    branch: str = "",
    name: str = "",
):
    """Create a new worktree and launch Claude.

    Parameters
    ----------
    query : str
        Query to send to Claude
    branch : str
        Source branch to create worktree from
    name : str
        Name suffix for the worktree branch
    """
    # Get repo root
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=True,
    )
    repo_root = Path(result.stdout.strip())

    # Check if .claude-wt/worktrees is in .gitignore
    if not check_gitignore(repo_root):
        panel_content = """Claude-wt creates worktrees in your repo at [cyan].claude-wt/worktrees[/cyan].

This directory must be added to .gitignore to prevent committing worktree data.

[yellow]→[/yellow] Please run [bold]claude-wt init[/bold] to automatically add .claude-wt/worktrees to .gitignore"""

        console.print(
            Panel(
                panel_content,
                title="[bold red]⚠️  Setup Required[/bold red]",
                border_style="red",
                width=60,
            )
        )
        raise SystemExit(1)

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

    # Sync with origin
    subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True)
    subprocess.run(
        ["git", "-C", str(repo_root), "switch", "--quiet", source_branch], check=True
    )
    subprocess.run(
        ["git", "-C", str(repo_root), "pull", "--ff-only", "--quiet"], check=True
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

    # Setup worktree path
    wt_path = repo_root / ".claude-wt" / "worktrees" / branch_name
    wt_path.parent.mkdir(parents=True, exist_ok=True)

    # Create worktree if needed
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
                branch_name,
            ],
            check=True,
        )

    # Print helpful info
    panel_content = f"""[dim]Source branch:[/dim] [cyan]{source_branch}[/cyan]

[green]🟢 Resume this session:[/green] [bold]claude-wt resume {suffix}[/bold]
[blue]🧹 Delete this session:[/blue] [bold]claude-wt clean {suffix}[/bold]
[red]🧨 Delete all sessions:[/red] [bold]claude-wt clean --all[/bold]"""

    console.print(
        Panel(
            panel_content,
            title="[bold cyan]Session Created[/bold cyan]",
            border_style="cyan",
            expand=False,
        )
    )

    # Launch Claude using custom monitor script
    claude_script = "/home/decoder/dev/dotfiles/scripts/__claude_with_monitor.sh"
    claude_cmd = [claude_script, "--add-dir", str(repo_root)]
    if query:
        claude_cmd.extend(["--", query])

    subprocess.run(claude_cmd, cwd=wt_path)


@app.command
def resume(branch_name: str):
    """Resume an existing worktree session.

    Parameters
    ----------
    branch_name : str
        Branch name to resume
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

        # Find worktree path using git
        full_branch_name = f"claude-wt-{branch_name}"
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse worktree list to find the matching branch
        wt_path = None
        current_wt = {}
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current_wt and current_wt.get("branch") == full_branch_name:
                    wt_path = Path(current_wt["path"])
                    break
                current_wt = {"path": line[9:]}
            elif line.startswith("branch "):
                current_wt["branch"] = line[7:]

        # Check the last worktree entry
        if current_wt and current_wt.get("branch") == full_branch_name:
            wt_path = Path(current_wt["path"])

        if not wt_path or not wt_path.exists():
            console.print(
                f"[red]Error: Worktree for branch '{branch_name}' not found[/red]"
            )
            raise SystemExit(1)

        console.print(
            f"[yellow]🔄 Resuming session for branch:[/yellow] [bold]{branch_name}[/bold]"
        )

        # Launch Claude with --continue to resume conversation
        claude_script = "/home/decoder/dev/dotfiles/scripts/__claude_with_monitor.sh"
        claude_cmd = [claude_script, "--add-dir", str(repo_root), "--continue"]
        subprocess.run(claude_cmd, cwd=wt_path)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def clean(
    branch_name: str = "",
    all: bool = False,
):
    """Delete claude-wt worktrees and branches.

    Parameters
    ----------
    branch_name : str
        Specific branch to clean
    all : bool
        Clean all claude-wt sessions
    """
    try:
        # Require either branch_name or --all
        if not branch_name and not all:
            console.print(
                "[red]Error: Must specify either a branch name or --all flag[/red]"
            )
            raise SystemExit(1)

        if branch_name and all:
            console.print(
                "[red]Error: Cannot specify both branch name and --all flag[/red]"
            )
            raise SystemExit(1)

        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
        wt_root = repo_root / ".claude-wt" / "worktrees"

        if branch_name:
            # Clean specific branch
            full_branch_name = f"claude-wt-{branch_name}"
            wt_path = wt_root / full_branch_name

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
                        
                        # Check if this is a claude-wt worktree by branch name or path
                        is_claude_wt = (
                            branch_name.startswith("claude-wt-") or 
                            "/.claude-wt/worktrees/" in wt_path
                        )
                        
                        if is_claude_wt:
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
                            except subprocess.CalledProcessError as e:
                                console.print(
                                    f"  [red]❌ Failed to remove worktree: {branch_name or wt_path}[/red]"
                                )
                                # Try to prune if removal failed
                                try:
                                    subprocess.run(
                                        ["git", "-C", str(repo_root), "worktree", "prune"],
                                        check=True,
                                    )
                                except:
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


@app.command
def list():
    """List all claude-wt worktrees."""
    try:
        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
        repo_name = repo_root.name

        # Get all worktrees from git
        result = subprocess.run(
            ["git", "-C", str(repo_root), "worktree", "list", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )

        # Parse worktree list output
        worktrees = []
        current_wt = {}
        for line in result.stdout.split("\n"):
            if line.startswith("worktree "):
                if current_wt:
                    worktrees.append(current_wt)
                current_wt = {"path": line[9:]}  # Remove 'worktree ' prefix
            elif line.startswith("branch "):
                current_wt["branch"] = line[7:]  # Remove 'branch ' prefix
        if current_wt:
            worktrees.append(current_wt)

        # Filter for claude-wt worktrees
        claude_worktrees = [
            wt for wt in worktrees if wt.get("branch", "").startswith("claude-wt-")
        ]

        if not claude_worktrees:
            console.print("[yellow]No claude-wt worktrees found.[/yellow]")
            return

        # Create table
        table = Table(
            title=f"Claude-wt worktrees for [bold cyan]{repo_name}[/bold cyan]"
        )
        table.add_column("Status", style="green", justify="center")
        table.add_column("Session", style="cyan", min_width=15)
        table.add_column("Path", style="dim", overflow="fold")

        for wt in sorted(claude_worktrees, key=lambda x: x.get("branch", "")):
            branch_name = wt.get("branch", "")
            suffix = branch_name.replace("claude-wt-", "")
            wt_path = wt["path"]

            # Check if worktree path still exists
            status = "[green]✅[/green]" if Path(wt_path).exists() else "[red]❌[/red]"

            table.add_row(status, suffix, wt_path)

        console.print(table)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def init():
    """Initialize claude-wt for this repository."""
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
def resume_issue(branch_name: str):
    """Resume an issue-based worktree session.

    Parameters
    ----------
    branch_name : str
        Issue branch name (e.g., doc-856/fix-stuff)
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

        # Find worktree path
        wt_path = repo_root / ".claude-wt" / "worktrees" / branch_name.replace("/", "-")

        if not wt_path.exists():
            console.print(
                f"[red]Error: Worktree for branch '{branch_name}' not found[/red]"
            )
            raise SystemExit(1)

        console.print(
            f"[yellow]🔄 Resuming session for issue branch:[/yellow] [bold]{branch_name}[/bold]"
        )

        # Launch Claude with --continue to resume conversation
        claude_script = "/home/decoder/dev/dotfiles/scripts/__claude_with_monitor.sh"
        claude_cmd = [claude_script, "--add-dir", str(repo_root), "--continue"]
        subprocess.run(claude_cmd, cwd=wt_path)

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def clean_issue(branch_name: str):
    """Delete an issue-based worktree and optionally its branch.

    Parameters
    ----------
    branch_name : str
        Issue branch name to clean (e.g., doc-856/fix-stuff)
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
        
        # Find worktree path
        wt_path = repo_root / ".claude-wt" / "worktrees" / branch_name.replace("/", "-")

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
        else:
            console.print(f"[yellow]⚠️  Worktree for {branch_name} not found[/yellow]")

        # Ask if they want to delete the branch
        delete_branch = console.input(
            f"[yellow]Do you want to delete the branch '{branch_name}'? (y/N):[/yellow] "
        ).lower() == 'y'
        
        if delete_branch:
            try:
                subprocess.run(
                    ["git", "-C", str(repo_root), "branch", "-D", branch_name],
                    check=True,
                )
                console.print(f"[green]✅ Deleted branch:[/green] {branch_name}")
            except subprocess.CalledProcessError:
                console.print(
                    f"[yellow]⚠️  Could not delete branch {branch_name} (may be checked out elsewhere)[/yellow]"
                )

    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def version():
    """Show version information."""
    console.print("claude-wt 0.1.0")


@app.command
def from_issue(query: str = ""):
    """Create a worktree from a Linear issue and launch Claude.
    
    Parameters
    ----------
    query : str
        Optional query to send to Claude
    """
    try:
        # Check for required environment variables
        if not os.environ.get("LINEAR_API_KEY"):
            console.print("[red]Error: LINEAR_API_KEY environment variable not set[/red]")
            raise SystemExit(1)
        
        if not os.environ.get("LINEAR_USER_ID"):
            console.print("[red]Error: LINEAR_USER_ID environment variable not set[/red]")
            raise SystemExit(1)
        
        # Get repo root
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        repo_root = Path(result.stdout.strip())
        
        # Check gitignore setup
        if not check_gitignore(repo_root):
            panel_content = """Claude-wt creates worktrees in your repo at [cyan].claude-wt/worktrees[/cyan].

This directory must be added to .gitignore to prevent committing worktree data.

[yellow]→[/yellow] Please run [bold]claude-wt init[/bold] to automatically add .claude-wt/worktrees to .gitignore"""

            console.print(
                Panel(
                    panel_content,
                    title="[bold red]⚠️  Setup Required[/bold red]",
                    border_style="red",
                    width=60,
                )
            )
            raise SystemExit(1)
        
        # Fetch Linear issues
        console.print("[cyan]Fetching Linear issues...[/cyan]")
        
        graphql_query = {
            "query": f"""query {{ 
                user(id: "{os.environ['LINEAR_USER_ID']}") {{ 
                    id 
                    name 
                    assignedIssues(filter: {{ state: {{ name: {{ nin: ["Released", "Canceled"] }} }} }}) {{ 
                        nodes {{ 
                            id 
                            title 
                            url 
                        }} 
                    }} 
                }} 
            }}"""
        }
        
        # Use curl to fetch issues (matching the bfi script approach)
        curl_cmd = [
            "curl", "-s", "-X", "POST",
            "-H", "Content-Type: application/json",
            "-H", f"Authorization: {os.environ['LINEAR_API_KEY']}",
            "--data", json.dumps(graphql_query),
            "https://api.linear.app/graphql"
        ]
        
        result = subprocess.run(curl_cmd, capture_output=True, text=True, check=True)
        
        try:
            response = json.loads(result.stdout)
        except json.JSONDecodeError:
            console.print(f"[red]Error: Invalid JSON response from Linear API[/red]")
            raise SystemExit(1)
        
        if "errors" in response:
            console.print(f"[red]Error from Linear API: {response['errors']}[/red]")
            raise SystemExit(1)
        
        issues = response.get("data", {}).get("user", {}).get("assignedIssues", {}).get("nodes", [])
        
        if not issues:
            console.print("[yellow]No assigned issues found[/yellow]")
            raise SystemExit(1)
        
        # Process all issues without filtering by existing branches
        filtered_issues = []
        for issue in issues:
            # Extract issue ID from URL (e.g., ABC-123)
            issue_id = issue["url"].split("/")[-2].replace("[", "").replace("]", "").lower()
            
            filtered_issues.append({
                "id": issue_id,
                "title": issue["title"],
                "url": issue["url"],
                "display": f"{issue['title']} ({issue['url']})"
            })
        
        if not filtered_issues:
            console.print("[yellow]No assigned issues found[/yellow]")
            raise SystemExit(1)
        
        # Use fzf to select an issue
        fzf_input = "\n".join([issue["display"] for issue in filtered_issues])
        
        try:
            result = subprocess.run(
                ["fzf", "--height", "40%", "--reverse"],
                input=fzf_input,
                capture_output=True,
                text=True,
                check=True,
            )
            selected_display = result.stdout.strip()
        except subprocess.CalledProcessError:
            console.print("[yellow]No issue selected[/yellow]")
            raise SystemExit(1)
        
        # Find the selected issue
        selected_issue = None
        for issue in filtered_issues:
            if issue["display"] == selected_display:
                selected_issue = issue
                break
        
        if not selected_issue:
            console.print("[red]Error: Could not find selected issue[/red]")
            raise SystemExit(1)
        
        # Prompt for branch name suffix
        console.print(f"\n[cyan]Selected issue:[/cyan] {selected_issue['id']}")
        branch_suffix = console.input("[green]Enter a name for your branch: [/green]")
        
        if not branch_suffix:
            console.print("[yellow]No branch name provided[/yellow]")
            raise SystemExit(1)
        
        # Create the branch name (issue-id/branch-suffix)
        issue_branch_name = f"{selected_issue['id']}/{branch_suffix}"
        
        # Switch to main and pull latest
        subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "checkout", "main"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "pull", "--ff-only", "--quiet"], check=True)
        
        # Create the issue branch if it doesn't exist (but don't checkout)
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show-ref",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{issue_branch_name}",
                ],
                check=True,
            )
            console.print(f"[yellow]Branch {issue_branch_name} already exists, using it[/yellow]")
        except subprocess.CalledProcessError:
            # Branch doesn't exist, create it from main without checking out
            subprocess.run(
                ["git", "-C", str(repo_root), "branch", issue_branch_name, "main"],
                check=True,
            )
        
        # Setup worktree path - use branch name directly
        wt_path = repo_root / ".claude-wt" / "worktrees" / issue_branch_name.replace("/", "-")
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create worktree directly from the issue branch
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
                    issue_branch_name,
                ],
                check=True,
            )
        
        # Print helpful info
        panel_content = f"""[dim]Issue:[/dim] [cyan]{selected_issue['id']}[/cyan] - {selected_issue['title']}
[dim]Branch:[/dim] [cyan]{issue_branch_name}[/cyan]
[dim]Worktree:[/dim] [cyan]{wt_path.name}[/cyan]

[green]🟢 Resume this session:[/green] [bold]claude-wt resume-issue {selected_issue['id']}/{branch_suffix}[/bold]
[blue]🧹 Delete this session:[/blue] [bold]claude-wt clean-issue {selected_issue['id']}/{branch_suffix}[/bold]"""

        console.print(
            Panel(
                panel_content,
                title="[bold cyan]Session Created from Linear Issue[/bold cyan]",
                border_style="cyan",
                expand=False,
            )
        )
        
        # Fetch full issue details using the get_linear_issue script
        console.print(f"[cyan]Fetching full issue details for {selected_issue['id']}...[/cyan]")
        
        get_issue_script = "/home/decoder/dev/dotfiles/scripts/__get_linear_issue.sh"
        try:
            result = subprocess.run(
                [get_issue_script, selected_issue['id']],
                capture_output=True,
                text=True,
                check=True,
            )
            issue_details = result.stdout
            
            # Prepare initial query with full issue context
            initial_query = f"Here is the Linear issue I'm working on:\n\n{issue_details}"
            if query:
                initial_query = f"{initial_query}\n\nAdditional context from user: {query}"
        except subprocess.CalledProcessError as e:
            console.print(f"[yellow]Warning: Could not fetch full issue details, using basic info[/yellow]")
            # Fallback to basic info
            initial_query = f"I'm working on Linear issue {selected_issue['id']}: {selected_issue['title']}. URL: {selected_issue['url']}"
            if query:
                initial_query = f"{initial_query}\n\n{query}"
        
        # Launch Claude with issue context
        claude_script = "/home/decoder/dev/dotfiles/scripts/__claude_with_monitor.sh"
        claude_cmd = [claude_script, "--add-dir", str(repo_root), "--", initial_query]
        
        subprocess.run(claude_cmd, cwd=wt_path)
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        raise SystemExit(1)


@app.command
def from_issue_noninteractive(issue_id: str, branch_name: str, query: str = ""):
    """Create a worktree from a Linear issue ID non-interactively.
    
    Parameters
    ----------
    issue_id : str
        Linear issue ID (e.g., DOC-856)
    branch_name : str
        Branch name suffix
    query : str
        Optional query to send to Claude
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
        
        # Check gitignore setup
        if not check_gitignore(repo_root):
            console.print("[red]Error: .claude-wt/worktrees not in .gitignore. Run 'claude-wt init' first[/red]")
            raise SystemExit(1)
        
        # Create the branch name (issue-id/branch-suffix)
        issue_branch_name = f"{issue_id.lower()}/{branch_name}"
        
        # Switch to main and pull latest
        subprocess.run(["git", "-C", str(repo_root), "fetch", "origin"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "checkout", "main"], check=True)
        subprocess.run(["git", "-C", str(repo_root), "pull", "--ff-only", "--quiet"], check=True)
        
        # Create the issue branch if it doesn't exist
        try:
            subprocess.run(
                [
                    "git",
                    "-C",
                    str(repo_root),
                    "show-ref",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{issue_branch_name}",
                ],
                check=True,
            )
            console.print(f"[yellow]Branch {issue_branch_name} already exists, using it[/yellow]")
        except subprocess.CalledProcessError:
            # Branch doesn't exist, create it from main
            subprocess.run(
                ["git", "-C", str(repo_root), "branch", issue_branch_name, "main"],
                check=True,
            )
        
        # Setup worktree path
        wt_path = repo_root / ".claude-wt" / "worktrees" / issue_branch_name.replace("/", "-")
        wt_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create worktree if it doesn't exist
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
                    issue_branch_name,
                ],
                check=True,
            )
            console.print(f"[green]Created worktree at {wt_path}[/green]")
        else:
            console.print(f"[yellow]Worktree already exists at {wt_path}[/yellow]")
        
        # Output the worktree path for the hook to use
        # This is the only output that should go to stdout for the hook to parse
        print(str(wt_path))
        
        # Don't launch Claude here - let the hook handle launching the tmuxinator session
        # which will set up the proper environment
        
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Error: {e}[/red]", file=sys.stderr)
        raise SystemExit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    app()
