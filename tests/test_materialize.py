"""Tests for materialize command (convert existing branch to worktree).

Following FIRST principles:
- Fast: No real git operations (mocked)
- Isolated: Each test independent
- Repeatable: Deterministic outcomes
- Self-Checking: Clear assertions
- Timely: Quick to execute
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from claude_wt.worktree import materialize_branch


class TestMaterializeBranch:
    """Test materialize command that creates worktree from existing branch."""

    @pytest.fixture
    def mock_repo_root(self, tmp_path):
        """Mock repository root path."""
        repo_root = tmp_path / "test-repo"
        repo_root.mkdir()
        return repo_root

    @pytest.fixture
    def mock_worktree_base(self, tmp_path):
        """Mock worktree base directory."""
        wt_base = tmp_path / "worktrees"
        wt_base.mkdir()
        return wt_base

    @patch("claude_wt.worktree.create_tmux_session")
    @patch("claude_wt.worktree.install_branch_protection_hook")
    @patch("claude_wt.worktree.copy_gitignored_files")
    @patch("claude_wt.worktree.create_worktree_context")
    @patch("claude_wt.worktree.get_worktree_base")
    @patch("claude_wt.worktree.subprocess.run")
    def test_creates_worktree_from_existing_branch(
        self,
        mock_run,
        mock_get_base,
        mock_context,
        mock_copy_files,
        mock_install_hook,
        mock_tmux,
        mock_repo_root,
        mock_worktree_base,
    ):
        """Test creating worktree from existing local branch.

        BEHAVIOR: materialize should create worktree from an existing
        local branch and launch Claude in tmux session.
        """
        # ARRANGE
        mock_get_base.return_value = mock_worktree_base
        mock_run.side_effect = [
            Mock(returncode=0, stdout=str(mock_repo_root)),  # git rev-parse
            Mock(returncode=0),  # git show-ref (branch exists)
            Mock(returncode=0),  # git worktree add
        ]

        # ACT
        materialize_branch("feature/test-branch")

        # ASSERT
        # Verify git show-ref was called to check branch exists
        show_ref_calls = [
            call for call in mock_run.call_args_list
            if call[0] and "show-ref" in str(call[0][0])
        ]
        assert len(show_ref_calls) == 1, "Should verify branch exists"

        # Verify worktree was created
        worktree_add_calls = [
            call for call in mock_run.call_args_list
            if call[0] and "worktree" in str(call[0][0]) and "add" in str(call[0][0])
        ]
        assert len(worktree_add_calls) == 1, "Should create worktree"

        # Verify required functions were called
        assert mock_copy_files.called, "Should copy gitignored files"
        assert mock_install_hook.called, "Should install branch protection hook"
        assert mock_context.called, "Should create worktree context"
        assert mock_tmux.called, "Should create tmux session"

    @patch("claude_wt.worktree.subprocess.run")
    def test_rejects_nonexistent_branch(
        self,
        mock_run,
        mock_repo_root,
    ):
        """Test rejection of non-existent branch.

        BEHAVIOR: If branch doesn't exist locally, should error with
        clear message without creating worktree.
        """
        # ARRANGE
        from subprocess import CalledProcessError
        mock_run.side_effect = [
            Mock(returncode=0, stdout=str(mock_repo_root), stderr=""),  # git rev-parse
            CalledProcessError(1, ["git", "show-ref"]),  # git show-ref (branch doesn't exist)
        ]

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            materialize_branch("nonexistent-branch")

        assert exc_info.value.code == 1, "Should exit with error code"

        # Verify git show-ref was called (to check branch)
        assert mock_run.call_count >= 2, "Should check if branch exists"
        show_ref_call = mock_run.call_args_list[1]
        assert "show-ref" in str(show_ref_call), "Should verify branch with show-ref"

    @patch("claude_wt.worktree.create_tmux_session")
    @patch("claude_wt.worktree.install_branch_protection_hook")
    @patch("claude_wt.worktree.copy_gitignored_files")
    @patch("claude_wt.worktree.create_worktree_context")
    @patch("claude_wt.worktree.get_worktree_base")
    @patch("claude_wt.worktree.subprocess.run")
    def test_sanitizes_branch_name_with_slashes(
        self,
        mock_run,
        mock_get_base,
        mock_context,
        mock_copy_files,
        mock_install_hook,
        mock_tmux,
        mock_repo_root,
        mock_worktree_base,
    ):
        """Test that slashes in branch names are converted to hyphens.

        BEHAVIOR: Filesystem paths cannot contain slashes, so branch
        names like 'feature/auth' become 'test-repo-feature-auth'.
        """
        # ARRANGE
        mock_get_base.return_value = mock_worktree_base
        mock_run.side_effect = [
            Mock(returncode=0, stdout=str(mock_repo_root)),  # git rev-parse
            Mock(returncode=0),  # git show-ref
            Mock(returncode=0),  # git worktree add
        ]

        # ACT
        materialize_branch("feature/auth/oauth")

        # ASSERT
        # Verify worktree path doesn't contain slashes
        worktree_add_call = [
            call for call in mock_run.call_args_list
            if call[0] and "worktree" in str(call[0][0]) and "add" in str(call[0][0])
        ][0]

        wt_path_arg = str(worktree_add_call[0][0][3])  # 4th argument is path
        assert "feature-auth-oauth" in wt_path_arg, "Slashes should be converted to hyphens"
        assert "feature/auth" not in wt_path_arg, "Path should not contain slashes"

    @patch("claude_wt.worktree.create_tmux_session")
    @patch("claude_wt.worktree.get_worktree_base")
    @patch("claude_wt.worktree.subprocess.run")
    def test_resumes_existing_worktree(
        self,
        mock_run,
        mock_get_base,
        mock_tmux,
        mock_repo_root,
        mock_worktree_base,
    ):
        """Test that existing worktree is resumed without recreation.

        BEHAVIOR: If worktree already exists for branch, should resume
        the existing session instead of trying to create it again.
        """
        # ARRANGE
        existing_wt = mock_worktree_base / "test-repo-main"
        existing_wt.mkdir()

        mock_get_base.return_value = mock_worktree_base
        mock_run.side_effect = [
            Mock(returncode=0, stdout=str(mock_repo_root)),  # git rev-parse
            Mock(returncode=0),  # git show-ref
        ]

        # ACT
        materialize_branch("main")

        # ASSERT
        # Verify worktree add was NOT called (already exists)
        worktree_add_calls = [
            call for call in mock_run.call_args_list
            if call[0] and "worktree" in str(call[0][0]) and "add" in str(call[0][0])
        ]
        assert len(worktree_add_calls) == 0, "Should not recreate existing worktree"

        # Verify tmux session was still created (resume)
        assert mock_tmux.called, "Should create/resume tmux session"

    @patch("claude_wt.worktree.create_tmux_session")
    @patch("claude_wt.worktree.install_branch_protection_hook")
    @patch("claude_wt.worktree.copy_gitignored_files")
    @patch("claude_wt.worktree.create_worktree_context")
    @patch("claude_wt.worktree.get_worktree_base")
    @patch("claude_wt.worktree.subprocess.run")
    def test_creates_session_name_from_branch(
        self,
        mock_run,
        mock_get_base,
        mock_context,
        mock_copy_files,
        mock_install_hook,
        mock_tmux,
        mock_repo_root,
        mock_worktree_base,
    ):
        """Test that tmux session name follows naming convention.

        BEHAVIOR: Session name should be 'wt-{repo}-{safe-branch}'
        to match other claude-wt sessions.
        """
        # ARRANGE
        mock_get_base.return_value = mock_worktree_base
        mock_run.side_effect = [
            Mock(returncode=0, stdout=str(mock_repo_root)),  # git rev-parse
            Mock(returncode=0),  # git show-ref
            Mock(returncode=0),  # git worktree add
        ]

        # ACT
        materialize_branch("doc-123-feature")

        # ASSERT
        assert mock_tmux.called, "Should create tmux session"
        session_name = mock_tmux.call_args[0][0]
        assert session_name.startswith("wt-"), "Session should start with wt-"
        assert "test-repo" in session_name, "Session should include repo name"
        assert "doc-123-feature" in session_name, "Session should include branch name"
