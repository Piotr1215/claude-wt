"""Tests for unified work command.

Following TDD methodology:
1. Write tests first
2. Implement minimal code to pass
3. Refactor while keeping tests green
4. Keep cyclomatic complexity low (< 5 per function)
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest


class TestIdentifierDetection:
    """Test automatic detection of identifier types.

    BEHAVIOR: Should detect Linear issues, GitHub PRs, or custom branches.
    Each detector should be a simple function with CC=1 (no branching).
    """

    def test_detects_linear_issue_uppercase(self):
        """Detect Linear issue IDs in uppercase format.

        BEHAVIOR: DOC-123, ENG-456, PLAT-789 should be detected as Linear.
        """
        from claude_wt.identifier import is_linear_issue

        assert is_linear_issue("DOC-123") is True
        assert is_linear_issue("ENG-456") is True
        assert is_linear_issue("PLAT-789") is True

    def test_detects_linear_issue_lowercase(self):
        """Detect Linear issue IDs in lowercase format.

        BEHAVIOR: doc-123, eng-456 should be detected as Linear.
        """
        from claude_wt.identifier import is_linear_issue

        assert is_linear_issue("doc-123") is True
        assert is_linear_issue("eng-456") is True

    def test_detects_linear_issue_mixed_case(self):
        """Detect Linear issue IDs in mixed case format.

        BEHAVIOR: Doc-123, eNg-456 should be detected as Linear.
        """
        from claude_wt.identifier import is_linear_issue

        assert is_linear_issue("Doc-123") is True
        assert is_linear_issue("eNg-456") is True

    def test_rejects_non_linear_patterns(self):
        """Reject strings that don't match Linear pattern.

        BEHAVIOR: PR-123, 123, feature-branch should return False.
        """
        from claude_wt.identifier import is_linear_issue

        assert is_linear_issue("PR-123") is False
        assert is_linear_issue("123") is False
        assert is_linear_issue("feature-branch") is False
        assert is_linear_issue("") is False

    def test_detects_pr_number_plain(self):
        """Detect plain PR numbers.

        BEHAVIOR: "123", "456" should be detected as PR numbers.
        """
        from claude_wt.identifier import is_pr_number

        assert is_pr_number("123") is True
        assert is_pr_number("456") is True

    def test_detects_pr_number_with_prefix(self):
        """Detect PR numbers with PR- prefix.

        BEHAVIOR: "PR-123", "pr-456" should be detected as PR numbers.
        """
        from claude_wt.identifier import is_pr_number

        assert is_pr_number("PR-123") is True
        assert is_pr_number("pr-456") is True

    def test_detects_pr_url(self):
        """Detect GitHub PR URLs.

        BEHAVIOR: Full GitHub URLs should be detected as PRs.
        """
        from claude_wt.identifier import is_pr_number

        url = "https://github.com/org/repo/pull/123"
        assert is_pr_number(url) is True

    def test_rejects_non_pr_patterns(self):
        """Reject strings that don't match PR patterns.

        BEHAVIOR: DOC-123, feature-branch should return False.
        """
        from claude_wt.identifier import is_pr_number

        assert is_pr_number("DOC-123") is False
        assert is_pr_number("feature-branch") is False
        assert is_pr_number("") is False

    def test_extracts_pr_number_from_plain(self):
        """Extract PR number from plain input.

        BEHAVIOR: "123" should return "123".
        """
        from claude_wt.identifier import extract_pr_number

        assert extract_pr_number("123") == "123"

    def test_extracts_pr_number_from_prefix(self):
        """Extract PR number from PR- prefix.

        BEHAVIOR: "PR-123" should return "123".
        """
        from claude_wt.identifier import extract_pr_number

        assert extract_pr_number("PR-123") == "123"
        assert extract_pr_number("pr-456") == "456"

    def test_extracts_pr_number_from_url(self):
        """Extract PR number from GitHub URL.

        BEHAVIOR: URL with /pull/123 should return "123".
        """
        from claude_wt.identifier import extract_pr_number

        url = "https://github.com/org/repo/pull/123"
        assert extract_pr_number(url) == "123"

    def test_normalizes_linear_issue_id(self):
        """Normalize Linear issue IDs to lowercase with prefix.

        BEHAVIOR: Any format should normalize to lowercase prefix format.
        """
        from claude_wt.identifier import normalize_linear_id

        assert normalize_linear_id("DOC-123") == "doc-123"
        assert normalize_linear_id("doc-123") == "doc-123"
        assert normalize_linear_id("ENG-456") == "eng-456"


class TestRepositoryResolution:
    """Test repository path resolution with clear precedence.

    BEHAVIOR: Follow explicit precedence order without fallbacks.
    Each resolution method should be a separate function with CC=1.
    """

    def test_uses_explicit_path_when_provided(self):
        """Use explicit --repo-path flag with highest priority.

        BEHAVIOR: Explicit path should be used without validation.
        """
        from claude_wt.repository import resolve_repo_path

        explicit = "/home/user/my-repo"
        result = resolve_repo_path(explicit_path=explicit)

        assert result == Path(explicit)

    def test_uses_uda_repo_path_field(self):
        """Use repo_path UDA field if no explicit path.

        BEHAVIOR: Should use UDA field when explicit path not provided.
        """
        from claude_wt.repository import resolve_repo_path

        uda = {"repo_path": "/home/user/task-repo"}
        result = resolve_repo_path(explicit_path=None, task_uda=uda)

        assert result == Path("/home/user/task-repo")

    def test_fails_for_unknown_repo_short_name(self):
        """Fail clearly when repo short name cannot be resolved.

        BEHAVIOR: Should raise error with helpful message.
        """
        from claude_wt.repository import RepositoryResolutionError, resolve_repo_path

        uda = {"repo": "unknown-repo"}

        with pytest.raises(RepositoryResolutionError) as exc_info:
            resolve_repo_path(explicit_path=None, task_uda=uda)

        assert "unknown-repo" in str(exc_info.value)
        assert "Cannot resolve" in str(exc_info.value)

    @patch("claude_wt.repository.subprocess.run")
    def test_uses_git_rev_parse_in_current_directory(self, mock_run):
        """Use git rev-parse when in git repo without explicit path.

        BEHAVIOR: Should detect repo root from current directory.
        """
        from claude_wt.repository import resolve_repo_path

        mock_run.return_value = Mock(stdout="/home/user/current-repo", returncode=0)

        result = resolve_repo_path(explicit_path=None, task_uda=None)

        assert result == Path("/home/user/current-repo")
        mock_run.assert_called_once()
        assert "git" in mock_run.call_args[0][0]
        assert "rev-parse" in mock_run.call_args[0][0]

    @patch("claude_wt.repository.subprocess.run")
    def test_fails_when_not_in_git_repo(self, mock_run):
        """Fail clearly when not in git repo and no path provided.

        BEHAVIOR: Should raise error with helpful message.
        """
        from claude_wt.repository import RepositoryResolutionError, resolve_repo_path

        mock_run.side_effect = Exception("not a git repository")

        with pytest.raises(RepositoryResolutionError) as exc_info:
            resolve_repo_path(explicit_path=None, task_uda=None)

        assert "Cannot determine repository" in str(exc_info.value)


class TestSessionNameGeneration:
    """Test consistent session name generation.

    BEHAVIOR: Generate predictable names from repo + identifier.
    Single function with CC=1 (no branching logic).
    """

    def test_generates_session_name_for_linear_issue(self):
        """Generate session name for Linear issue.

        BEHAVIOR: repo-name + linear-id in lowercase.
        """
        from claude_wt.session import generate_session_name

        result = generate_session_name("vcluster-docs", "DOC-123")
        assert result == "vcluster-docs-doc-123"

    def test_generates_session_name_for_pr(self):
        """Generate session name for PR.

        BEHAVIOR: repo-name + pr- + number.
        """
        from claude_wt.session import generate_session_name

        result = generate_session_name("vcluster-docs", "PR-456")
        assert result == "vcluster-docs-pr-456"

    def test_generates_session_name_for_custom_branch(self):
        """Generate session name for custom branch.

        BEHAVIOR: repo-name + sanitized-branch-name.
        """
        from claude_wt.session import generate_session_name

        result = generate_session_name("my-project", "feature/auth")
        assert result == "my-project-feature-auth"

    def test_sanitizes_slashes_in_session_names(self):
        """Replace slashes with dashes in session names.

        BEHAVIOR: Slashes should become dashes for tmux compatibility.
        """
        from claude_wt.session import generate_session_name

        result = generate_session_name("repo", "feature/sub/branch")
        assert "/" not in result
        assert result == "repo-feature-sub-branch"


class TestTmuxClaudeLauncher:
    """Test tmux session creation and Claude launching.

    BEHAVIOR: Reusable launcher for all workflows.
    Each tmux operation should be a separate function with CC=1-2.
    """

    @patch("claude_wt.tmux_launcher.subprocess.run")
    def test_creates_new_tmux_session_when_not_exists(self, mock_run):
        """Create new tmux session if it doesn't exist.

        BEHAVIOR: Should check existence, then create if needed.
        """
        from claude_wt.tmux_launcher import launch_claude_in_tmux

        # First call: has-session (returns 1 = doesn't exist)
        # Second call: new-session
        # Third call: send-keys
        # Fourth call: switch-client
        mock_run.side_effect = [
            Mock(returncode=1),  # has-session fails
            Mock(returncode=0),  # new-session succeeds
            Mock(returncode=0),  # send-keys succeeds
            Mock(returncode=0),  # switch-client succeeds
        ]

        launch_claude_in_tmux(
            session_name="test-session",
            worktree_path=Path("/tmp/worktree"),
            initial_prompt="Test prompt",
        )

        assert mock_run.call_count == 4
        # Verify has-session was called
        assert "has-session" in str(mock_run.call_args_list[0])
        # Verify new-session was called
        assert "new-session" in str(mock_run.call_args_list[1])

    @patch("claude_wt.tmux_launcher.subprocess.run")
    def test_reuses_existing_tmux_session(self, mock_run):
        """Reuse existing tmux session if it exists.

        BEHAVIOR: Should check existence, skip creation if exists.
        """
        from claude_wt.tmux_launcher import launch_claude_in_tmux

        # First call: has-session (returns 0 = exists)
        # Second call: send-keys (skip new-session)
        # Third call: switch-client
        mock_run.side_effect = [
            Mock(returncode=0),  # has-session succeeds
            Mock(returncode=0),  # send-keys succeeds
            Mock(returncode=0),  # switch-client succeeds
        ]

        launch_claude_in_tmux(
            session_name="existing-session",
            worktree_path=Path("/tmp/worktree"),
            initial_prompt="Test prompt",
        )

        assert mock_run.call_count == 3
        # Verify new-session was NOT called
        call_strings = [str(call) for call in mock_run.call_args_list]
        assert not any("new-session" in s for s in call_strings)

    @patch("claude_wt.tmux_launcher.subprocess.run")
    def test_launches_claude_with_correct_command(self, mock_run):
        """Launch Claude with correct flags and prompt.

        BEHAVIOR: Should use --dangerously-skip-permissions and --add-dir.
        """
        from claude_wt.tmux_launcher import launch_claude_in_tmux

        mock_run.return_value = Mock(returncode=0)

        worktree = Path("/tmp/test-worktree")
        prompt = "Work on feature X"

        launch_claude_in_tmux(
            session_name="test-session", worktree_path=worktree, initial_prompt=prompt
        )

        # Find the send-keys call
        send_keys_call = None
        for call in mock_run.call_args_list:
            if "send-keys" in str(call):
                send_keys_call = call
                break

        assert send_keys_call is not None
        call_args = send_keys_call[0][0]

        # Verify Claude command structure
        claude_cmd = " ".join(call_args)
        assert "--dangerously-skip-permissions" in claude_cmd
        assert "KUBECONFIG=/home/decoder/dev/homelab/kubeconfig" in claude_cmd
        assert "__claude_with_monitor.sh" in claude_cmd
        assert prompt in claude_cmd


class TestCyclomaticComplexity:
    """Verify all functions maintain low cyclomatic complexity.

    BEHAVIOR: No function should have CC > 5.
    This is a meta-test ensuring code quality.
    """

    def test_identifier_functions_have_low_complexity(self):
        """Identifier detection functions should have CC=1-2.

        BEHAVIOR: Simple regex matching, no branching.
        """
        # Each should be a simple one-liner with regex
        # CC=1 means: single entry, single exit, no branches
        import inspect

        from claude_wt.identifier import (
            extract_pr_number,
            is_linear_issue,
            is_pr_number,
            normalize_linear_id,
        )

        for func in [
            is_linear_issue,
            is_pr_number,
            extract_pr_number,
            normalize_linear_id,
        ]:
            source = inspect.getsource(func)
            # Count decision points (if, for, while, and, or, except)
            decisions = (
                source.count("if ")
                + source.count("elif ")
                + source.count("for ")
                + source.count("while ")
                + source.count(" and ")
                + source.count(" or ")
                + source.count("except ")
            )
            # CC = decisions + 1, should be <= 4 (allowing one guard clause)
            assert decisions <= 3, (
                f"{func.__name__} has too many decision points: {decisions}"
            )

    def test_repository_resolution_has_low_complexity(self):
        """Repository resolution should use strategy pattern, not nested ifs.

        BEHAVIOR: Each resolution method is separate, main function just chains.
        """
        import inspect

        from claude_wt.repository import resolve_repo_path

        source = inspect.getsource(resolve_repo_path)

        # Should have minimal branching - just precedence checks
        decisions = source.count("if ") + source.count("elif ")

        # Allow up to 4 decision points for precedence chain
        assert decisions <= 4, f"resolve_repo_path has too many branches: {decisions}"
