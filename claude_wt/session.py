"""Session name generation for tmux.

Simple, predictable session names from repo + identifier.
Cyclomatic Complexity: 1 (no branching)
"""


def generate_session_name(repo_name: str, identifier: str) -> str:
    """Generate consistent tmux session name.

    Format: {repo-name}-{sanitized-identifier}

    Examples:
    - ("vcluster-docs", "DOC-123") -> "vcluster-docs-DOC-123"
    - ("my-project", "PR-456") -> "my-project-PR-456"
    - ("repo", "feature/auth") -> "repo-feature-auth"

    Cyclomatic Complexity: 1 (single transformation)
    """
    sanitized = identifier.replace("/", "-")
    return f"{repo_name}-{sanitized}"
