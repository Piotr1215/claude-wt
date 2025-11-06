"""Repository path resolution with clear precedence.

Follows explicit precedence order:
1. Explicit --repo-path flag
2. UDA field 'repo_path'
3. UDA field 'repo' (rejected - must provide full path)
4. Current directory (git rev-parse)
5. ERROR - cannot determine

No fallbacks, no hardcoded paths, fail loudly.
Cyclomatic Complexity: 4 (precedence chain with 4 checks)
"""

import subprocess
from pathlib import Path


class RepositoryResolutionError(Exception):
    """Raised when repository path cannot be determined."""
    pass


def resolve_repo_path(
    explicit_path: str | None = None,
    task_uda: dict[str, str] | None = None,
) -> Path:
    """Resolve repository path with clear precedence.

    Precedence order:
    1. explicit_path parameter
    2. task_uda['repo_path']
    3. task_uda['repo'] -> ERROR (must provide full path)
    4. Current directory via git rev-parse
    5. ERROR

    Cyclomatic Complexity: 4 (4 if checks in precedence chain)

    Raises
    ------
    RepositoryResolutionError
        When repository path cannot be determined
    """
    # 1. Explicit path has highest priority
    if explicit_path:
        return Path(explicit_path).resolve()

    # 2. UDA field 'repo_path'
    if task_uda and task_uda.get("repo_path"):
        return Path(task_uda["repo_path"]).resolve()

    # 3. UDA field 'repo' is NOT supported - must provide full path
    if task_uda and task_uda.get("repo"):
        repo_name = task_uda["repo"]
        raise RepositoryResolutionError(
            f"Cannot resolve short name '{repo_name}'. "
            f"Please set 'repo_path' UDA field with full path. "
            f"Example: task {repo_name} modify repo_path:/full/path/to/{repo_name}"
        )

    # 4. Try current directory
    return _resolve_from_current_directory()


def _resolve_from_current_directory() -> Path:
    """Try to resolve repository from current working directory.

    Cyclomatic Complexity: 1 (no branching, raises on error)

    Raises
    ------
    RepositoryResolutionError
        When not in a git repository
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(result.stdout.strip())
    except (subprocess.CalledProcessError, Exception) as e:
        raise RepositoryResolutionError(
            "Cannot determine repository path. You must either:\n"
            "1. Run from within a git repository, OR\n"
            "2. Provide --repo-path flag, OR\n"
            "3. Set 'repo_path' UDA field in taskwarrior\n"
            f"Error: {e}"
        )
