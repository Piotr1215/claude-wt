"""Identifier detection and normalization.

Simple functions with CC=1-2 for detecting Linear issues, PRs, and custom branches.
Each function does ONE thing with minimal branching.
"""

import re


def is_linear_issue(identifier: str) -> bool:
    """Check if identifier matches Linear issue pattern.

    Pattern: 2-4 uppercase letters (NOT "PR"), hyphen, digits (e.g., DOC-123, ENG-456)
    Case-insensitive.
    Excludes "PR-123" pattern which is reserved for pull requests.

    Cyclomatic Complexity: 1 (no branching)
    """
    # Must be 2-4 letters + hyphen + digits, but NOT starting with "PR"
    if identifier.upper().startswith("PR-"):
        return False
    return bool(re.match(r"^[A-Z]{2,4}-\d+$", identifier, re.IGNORECASE))


def is_pr_number(identifier: str) -> bool:
    """Check if identifier is a GitHub PR number or URL.

    Matches:
    - Plain number: "123"
    - PR prefix: "PR-123", "pr-456"
    - GitHub URL: "https://github.com/org/repo/pull/123"

    Cyclomatic Complexity: 1 (no branching, just regex alternation)
    """
    pattern = r"^(\d+|PR-\d+|pr-\d+|https://github\.com/.*/pull/\d+)$"
    return bool(re.match(pattern, identifier, re.IGNORECASE))


def extract_pr_number(identifier: str) -> str:
    """Extract PR number from various formats.

    Handles:
    - Plain: "123" -> "123"
    - Prefix: "PR-123" -> "123"
    - URL: "https://github.com/org/repo/pull/123" -> "123"

    Cyclomatic Complexity: 1 (single regex extraction)
    """
    match = re.search(r"(\d+)", identifier)
    return match.group(1) if match else ""


def normalize_linear_id(issue_id: str) -> str:
    """Normalize Linear issue ID to lowercase format.

    Examples:
    - DOC-123 -> doc-123
    - eng-456 -> eng-456
    - Doc-789 -> doc-789

    Cyclomatic Complexity: 1 (simple transformation)
    """
    return issue_id.lower().replace("/", "-")


def detect_identifier_type(identifier: str) -> str:
    """Detect what type of identifier this is.

    Returns: "linear", "pr", or "custom"

    Cyclomatic Complexity: 3 (two if checks + implicit else)
    """
    if is_linear_issue(identifier):
        return "linear"
    if is_pr_number(identifier):
        return "pr"
    return "custom"
