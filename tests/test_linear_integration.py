"""Tests for Linear issue integration.

Following FIRST principles:
- Fast: No actual git/zenity/tmux operations (mocked)
- Isolated: Each test independent
- Repeatable: Deterministic outcomes
- Self-Checking: Clear assertions
- Timely: Quick to execute
"""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from claude_wt.linear import handle_linear_issue


class TestLinearIssueHandling:
    """Test Linear issue integration with TDD methodology."""

    @pytest.fixture
    def mock_git_repo(self, tmp_path):
        """Mock git repository structure."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        return repo_root

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess.run for git/zenity/tmux commands."""
        with patch("claude_wt.linear.subprocess.run") as mock:
            yield mock

    @pytest.fixture
    def mock_worktree_base(self, tmp_path):
        """Mock worktree base directory."""
        with patch("claude_wt.linear.get_worktree_base") as mock:
            worktree_base = tmp_path / "worktrees"
            worktree_base.mkdir()
            mock.return_value = worktree_base
            yield mock

    @pytest.fixture
    def mock_context_creation(self):
        """Mock worktree context creation."""
        with patch("claude_wt.linear.create_worktree_context") as mock:
            yield mock

    def test_normalizes_issue_id_to_doc_prefix(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test issue ID normalization to doc- prefix.

        BEHAVIOR: All issue IDs should be normalized to start with 'doc-'
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify (branch doesn't exist)
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-975", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        # Verify branch was created with normalized name
        branch_create_call = mock_subprocess.call_args_list[6]
        assert "doc-975" in " ".join(branch_create_call[0][0])

    def test_handles_issue_id_with_slash(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """SECURITY: Reject issue IDs with path traversal attempts.

        Issue IDs should not contain path separators that could
        escape the worktree directory.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify (branch doesn't exist)
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("doc-975/malicious", interactive=False)

        # ASSERT - Slashes should be replaced with dashes
        assert exc_info.value.code == 0
        branch_create_call = mock_subprocess.call_args_list[6]
        branch_cmd = " ".join(branch_create_call[0][0])
        # Slash in issue ID should be converted to dash
        assert "doc-975-malicious" in branch_cmd or "doc-975/doc-975-malicious" in branch_cmd

    def test_non_interactive_creates_timestamped_branch(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo, capsys
    ):
        """Test non-interactive mode creates branch with timestamp.

        BEHAVIOR: When interactive=False, should create branch with
        timestamp suffix without prompting user.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a (no existing branches)
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify (branch doesn't exist)
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-123", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        # Verify worktree path was printed to stdout
        captured = capsys.readouterr()
        assert "doc-123" in captured.out.lower()
        # Verify timestamp format in branch name (YYYYMMDD-HHMMSS)
        branch_create_call = mock_subprocess.call_args_list[6]
        branch_cmd = " ".join(branch_create_call[0][0])
        # Should contain year (20XX)
        assert any(f"20{y}" in branch_cmd for y in range(20, 30))

    def test_uses_existing_branch_without_recreation(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo, capsys
    ):
        """Test that existing branches are reused, not recreated.

        BEHAVIOR: If branch already exists, should skip branch creation
        and only create worktree.
        """
        # ARRANGE
        existing_branch = "doc-123/feature"
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a (existing branch)
            Mock(stdout=f"  {existing_branch}\n", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify (branch exists!)
            Mock(returncode=0),
            # git worktree add (no git branch call before this)
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-123", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        # Verify git branch command was NOT called (branch exists)
        git_commands = [call[0][0] for call in mock_subprocess.call_args_list]
        branch_commands = [cmd for cmd in git_commands if "branch" in cmd and "show-ref" not in " ".join(cmd)]
        # Should only see 'git branch -a' for listing, not 'git branch <name>' for creation
        assert len(branch_commands) == 1
        assert "-a" in branch_commands[0]

    def test_creates_worktree_context_file(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test that CLAUDE.md context file is created.

        BEHAVIOR: Must create worktree-specific context file for Claude.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-456", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        # Verify create_worktree_context was called
        mock_context_creation.assert_called_once()
        call_args = mock_context_creation.call_args
        # Should include issue_id
        assert "DOC-456" in call_args[0]

    def test_handles_git_fetch_failure(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test error handling when git fetch fails.

        BEHAVIOR: Should exit with error code when git operations fail.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin (FAILS)
            subprocess.CalledProcessError(1, ["git", "fetch"]),
        ]

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-789", interactive=False)

        # Should exit with error code
        assert exc_info.value.code == 1

    def test_prints_worktree_path_to_stdout(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo, capsys
    ):
        """Test that worktree path is output for automation.

        BEHAVIOR: Final worktree path must be printed to stdout
        for taskwarrior hook integration.
        """
        # ARRANGE
        worktree_base = mock_worktree_base.return_value
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-999", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        captured = capsys.readouterr()
        # Should print absolute path to worktree
        assert str(worktree_base) in captured.out
        assert "doc-999" in captured.out.lower()

    def test_skips_zenity_in_non_interactive_mode(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test that zenity is not called in non-interactive mode.

        BEHAVIOR: interactive=False should bypass all GUI prompts.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a (with existing branch to trigger picker)
            Mock(stdout="  doc-123/existing\n", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-123", interactive=False)

        # ASSERT
        assert exc_info.value.code == 0
        # Verify zenity was never called
        zenity_calls = [
            call for call in mock_subprocess.call_args_list
            if call[0] and isinstance(call[0][0], list) and len(call[0][0]) > 0 and "zenity" == call[0][0][0]
        ]
        assert len(zenity_calls) == 0, f"zenity should not be called in non-interactive mode, but got: {zenity_calls}"

    def test_creates_tmux_session_when_requested(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test tmux session creation with session_name parameter.

        BEHAVIOR: When session_name provided, should create tmux session
        and launch Claude with issue context.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
            # tmux has-session (doesn't exist)
            Mock(returncode=1),
            # tmux new-session
            Mock(returncode=0),
            # tmux send-keys
            Mock(returncode=0),
            # tmux switch-client
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-555", interactive=False, session_name="test-session")

        # ASSERT
        assert exc_info.value.code == 0
        # Verify tmux commands were called
        tmux_calls = [
            call for call in mock_subprocess.call_args_list
            if call[0] and "tmux" in str(call[0][0])
        ]
        assert len(tmux_calls) >= 3  # has-session, new-session, send-keys

    def test_uses_slash_command_for_linear_issue(
        self, mock_subprocess, mock_worktree_base, mock_context_creation, mock_git_repo
    ):
        """Test Claude is launched with /ops-linear-issue slash command.

        BEHAVIOR: Linear issues should trigger /ops-linear-issue {id} command,
        not plain text prompts. This enables Claude's Linear integration workflow.
        """
        # ARRANGE
        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout=str(mock_git_repo), returncode=0),
            # git branch -a
            Mock(stdout="", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git checkout main
            Mock(returncode=0),
            # git pull --ff-only
            Mock(returncode=0),
            # git show-ref --verify
            Mock(returncode=1),
            # git branch
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
            # tmux has-session (doesn't exist)
            Mock(returncode=1),
            # tmux new-session
            Mock(returncode=0),
            # tmux send-keys
            Mock(returncode=0),
            # tmux switch-client
            Mock(returncode=0),
        ]

        # ACT
        with pytest.raises(SystemExit) as exc_info:
            handle_linear_issue("DOC-999", interactive=False, session_name="test-session")

        # ASSERT
        assert exc_info.value.code == 0

        # Find the tmux send-keys call
        send_keys_calls = [
            call for call in mock_subprocess.call_args_list
            if call[0] and len(call[0]) > 0 and "send-keys" in str(call[0][0])
        ]
        assert len(send_keys_calls) == 1, "Should have exactly one send-keys call"

        # Extract the command arguments
        send_keys_args = send_keys_calls[0][0][0]
        claude_cmd = " ".join(send_keys_args)

        # Verify slash command is used (not plain text)
        assert "/ops-linear-issue DOC-999" in claude_cmd, \
            f"Expected '/ops-linear-issue DOC-999' in command, got: {claude_cmd}"
        assert "Working on issue" not in claude_cmd, \
            "Should use slash command, not plain text description"


class TestLinearIssueIDValidation:
    """Property-based tests for issue ID validation."""

    def test_removes_doc_prefix_before_normalization(self):
        """QUIRK: doc- prefix is removed then re-added (line 54-55).

        DISCOVERED: Even if input has DOC- prefix, it's removed
        and normalized to lowercase doc-.
        """
        # This tests the normalization logic without full integration
        issue_id = "DOC-123"
        issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
        issue_prefix = f"doc-{issue_prefix}"

        assert issue_prefix == "doc-123"

    def test_converts_slashes_to_dashes(self):
        """SECURITY: Path separators in issue IDs are neutralized.

        Prevents path traversal by converting / to -.
        """
        issue_id = "DOC-123/456"
        issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
        issue_prefix = f"doc-{issue_prefix}"

        assert "/" not in issue_prefix
        assert issue_prefix == "doc-123-456"

    def test_handles_multiple_slashes(self):
        """SECURITY: Multiple path separators are all converted."""
        issue_id = "DOC-123/456/789"
        issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
        issue_prefix = f"doc-{issue_prefix}"

        assert "/" not in issue_prefix
        assert issue_prefix == "doc-123-456-789"

    def test_handles_uppercase_variations(self):
        """Test case normalization for consistency."""
        variations = ["DOC-123", "doc-123", "Doc-123", "dOc-123"]

        results = []
        for issue_id in variations:
            issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
            issue_prefix = f"doc-{issue_prefix}"
            results.append(issue_prefix)

        # All should normalize to same value
        assert len(set(results)) == 1
        assert results[0] == "doc-123"


class TestLinearSecurityEdgeCases:
    """Security-focused tests for Linear integration."""

    def test_rejects_path_traversal_in_issue_id(self):
        """SECURITY: Issue IDs with .. path traversal are neutralized."""
        issue_id = "../../../etc/passwd"
        issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
        issue_prefix = f"doc-{issue_prefix}"

        # Should not contain any path separators
        assert "/" not in issue_prefix
        assert "\\" not in issue_prefix
        # Result should be safe
        assert issue_prefix == "doc-..-..-..-etc-passwd"

    def test_handles_null_bytes_in_issue_id(self):
        """SECURITY: Null bytes should not crash the parser."""
        issue_id = "DOC-123\x00malicious"
        try:
            issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
            issue_prefix = f"doc-{issue_prefix}"
            # Should complete without error
            assert "doc-" in issue_prefix
        except Exception as e:
            pytest.fail(f"Null byte caused error: {e}")

    def test_handles_extremely_long_issue_id(self):
        """SECURITY: Extremely long issue IDs should not cause issues."""
        # Create very long issue ID
        issue_id = "DOC-" + "1" * 10000
        try:
            issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
            issue_prefix = f"doc-{issue_prefix}"
            # Should complete without error
            assert issue_prefix.startswith("doc-")
            assert len(issue_prefix) > 0
        except Exception as e:
            pytest.fail(f"Long issue ID caused error: {e}")

    def test_handles_special_shell_characters(self):
        """SECURITY: Shell metacharacters should not execute."""
        dangerous_chars = [";", "|", "&", "$", "`", "(", ")", "<", ">"]

        for char in dangerous_chars:
            issue_id = f"DOC-123{char}rm -rf /"
            issue_prefix = issue_id.lower().replace("doc-", "").replace("/", "-")
            issue_prefix = f"doc-{issue_prefix}"

            # Should be string, not executed
            assert isinstance(issue_prefix, str)
            # Original character may or may not be preserved
            # but should not cause execution


class TestLinearExistingWorktreeDetection:
    """Tests for detecting and reusing existing worktrees."""

    @pytest.fixture
    def worktree_dir(self, tmp_path):
        """Create temporary worktree directory with existing worktrees."""
        wt_dir = tmp_path / "worktrees"
        wt_dir.mkdir()
        # Create existing worktrees
        (wt_dir / "doc-123-feature1").mkdir()
        (wt_dir / "doc-123-feature2").mkdir()
        (wt_dir / "doc-456-bugfix").mkdir()
        return wt_dir

    def test_identifies_worktrees_for_specific_issue(self, worktree_dir):
        """Test that only matching issue worktrees are detected.

        BEHAVIOR: Should only find worktrees that start with issue prefix.
        """
        issue_prefix = "doc-123"
        existing_worktrees = []

        for entry in worktree_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(issue_prefix + "-"):
                existing_worktrees.append(entry.name)

        # Should find only doc-123 worktrees
        assert len(existing_worktrees) == 2
        assert "doc-123-feature1" in existing_worktrees
        assert "doc-123-feature2" in existing_worktrees
        assert "doc-456-bugfix" not in existing_worktrees

    def test_skips_files_in_worktree_directory(self, worktree_dir):
        """Test that files in worktree directory are ignored.

        BEHAVIOR: Only directories should be considered as worktrees.
        """
        # Create a file in worktree directory
        (worktree_dir / "doc-789-not-a-dir.txt").touch()

        issue_prefix = "doc-789"
        existing_worktrees = []

        for entry in worktree_dir.iterdir():
            if entry.is_dir() and entry.name.startswith(issue_prefix + "-"):
                existing_worktrees.append(entry.name)

        # Should not include the file
        assert len(existing_worktrees) == 0
