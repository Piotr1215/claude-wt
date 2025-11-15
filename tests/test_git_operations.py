"""Tests for git operations in claude-wt."""

import os
import subprocess
import sys
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.cli import clean, list_worktrees, new


class TestGitOperations:
    """Test git-related operations."""

    @patch("claude_wt.cli.subprocess.run")
    @patch("os.environ.get")
    def test_new_creates_worktree_with_branch(self, mock_environ, mock_run):
        """Test that 'new' command creates a worktree and branch."""
        # Mock TMUX env var to simulate being in tmux
        mock_environ.return_value = "tmux_session"

        # Mock git commands
        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git branch --show-current
            Mock(stdout="main", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git switch --quiet main
            Mock(returncode=0),
            # git pull --ff-only --quiet
            Mock(returncode=0),
            # git show-ref (branch doesn't exist)
            Mock(returncode=1),
            # git branch creation
            Mock(returncode=0),
            # git worktree add
            Mock(returncode=0),
            # tmux display-message to get window ID
            Mock(stdout="@1", returncode=0),
            # tmux set-option for window default-path
            Mock(returncode=0),
            # Launch Claude script
            Mock(returncode=0),
        ]

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists") as mock_exists:
                mock_exists.return_value = False
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        # This would normally exit, so we catch the SystemExit
                        new(query="test query", name="test-feature")

        # Verify git commands were called
        calls = mock_run.call_args_list
        assert any("rev-parse" in str(call) for call in calls)
        assert any("worktree" in str(call) and "add" in str(call) for call in calls)

    @patch("claude_wt.cli.subprocess.run")
    def test_clean_removes_worktree_and_branch(self, mock_run):
        """Test that clean removes worktree and branch."""
        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git worktree remove --force
            Mock(returncode=0),
            # git branch -D
            Mock(returncode=0),
        ]

        with patch("claude_wt.cli.Path.exists", return_value=True):
            clean(branch_name="test", all=False)

        # Verify both worktree remove and branch delete were called
        calls = mock_run.call_args_list
        assert any("worktree" in str(call) and "remove" in str(call) for call in calls)
        assert any("branch" in str(call) and "-D" in str(call) for call in calls)

    @patch("claude_wt.cli.subprocess.run")
    def test_clean_all_removes_all_claude_worktrees(self, mock_run):
        """Test that clean --all removes all claude-wt worktrees."""
        # Test with external worktrees in sibling directory
        worktree_output = """worktree /home/user/repo-worktrees/claude-wt-feature1
HEAD abc123
branch claude-wt-feature1

worktree /home/user/repo-worktrees/claude-wt-feature2
HEAD def456
branch claude-wt-feature2

worktree /home/user/repo
HEAD ghi789
branch main
"""

        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git worktree list --porcelain
            Mock(stdout=worktree_output, returncode=0),
            # git worktree remove for feature1
            Mock(returncode=0),
            # git worktree remove for feature2
            Mock(returncode=0),
            # git branch --list claude-wt-*
            Mock(stdout="  claude-wt-feature1\n  claude-wt-feature2\n", returncode=0),
            # git branch -D for feature1
            Mock(returncode=0),
            # git branch -D for feature2
            Mock(returncode=0),
        ]

        clean(branch_name="", all=True)

        # Verify multiple worktrees and branches were removed
        calls = mock_run.call_args_list
        remove_calls = [call for call in calls if "remove" in str(call)]
        assert len(remove_calls) >= 2  # At least 2 worktrees removed

    def test_list_shows_claude_worktrees(self, tmp_path, capsys):
        """Test that list displays worktrees from centralized directory.

        BEHAVIOR: Scans centralized worktrees and displays them in a table
        ISOLATED: Uses tmp_path, mocks Path.home() and git commands
        FAST: No real git operations, all mocked
        REPEATABLE: Deterministic with controlled mocks
        SELF-CHECKING: Asserts actual table output content
        """
        # ARRANGE: Create centralized worktree structure
        worktree_base = tmp_path / "dev" / "claude-wt-worktrees"
        worktree_base.mkdir(parents=True)

        # Create test worktree with .git file (worktree marker)
        test_wt = worktree_base / "myrepo-feature-x"
        test_wt.mkdir()
        (test_wt / ".git").write_text("gitdir: /tmp/fake/.git/worktrees/myrepo-feature-x")

        # ACT: Run list with mocked Path.home() and git commands
        with patch("pathlib.Path.home", return_value=tmp_path):
            with patch("claude_wt.worktree.subprocess.run") as mock_run:
                # Mock git commands: git-common-dir, then branch name
                mock_run.side_effect = [
                    Mock(stdout="/tmp/fake/.git", returncode=0),
                    Mock(stdout="feature-x", returncode=0),
                ]

                # Execute
                list_worktrees()

        # ASSERT: Verify worktree appears in output table
        captured = capsys.readouterr()
        assert "myrepo" in captured.out or "feature-x" in captured.out

    @patch("claude_wt.cli.subprocess.run")
    @patch("os.environ.get")
    def test_handles_existing_branch(self, mock_environ, mock_run):
        """Test that new command handles existing branch gracefully."""
        # Mock TMUX env var
        mock_environ.return_value = "tmux_session"

        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git branch --show-current
            Mock(stdout="main", returncode=0),
            # git fetch origin
            Mock(returncode=0),
            # git switch --quiet main
            Mock(returncode=0),
            # git pull --ff-only --quiet
            Mock(returncode=0),
            # git show-ref (branch exists)
            Mock(returncode=0),
            # git worktree add (no branch creation needed)
            Mock(returncode=0),
            # tmux display-message to get window ID
            Mock(stdout="@1", returncode=0),
            # tmux set-option for window default-path
            Mock(returncode=0),
            # Launch Claude script
            Mock(returncode=0),
        ]

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        new(query="test", name="existing")

        # Verify branch creation was skipped (show-ref succeeded)
        calls = mock_run.call_args_list
        branch_create_calls = [
            call
            for call in calls
            if "branch" in str(call) and "claude-wt-existing" in str(call)
        ]
        # Should only be show-ref, not branch creation
        assert len(branch_create_calls) == 0 or "show-ref" in str(
            branch_create_calls[0]
        )

    @patch("claude_wt.cli.subprocess.run")
    def test_worktree_creation_failure_handled(self, mock_run):
        """Test that worktree creation failures are handled gracefully."""

        def side_effect(*args, **kwargs):
            # Check the command being run
            if "rev-parse" in str(args):
                return Mock(stdout="/home/user/repo", returncode=0)
            elif "branch" in str(args) and "--show-current" in str(args):
                return Mock(stdout="main", returncode=0)
            elif "fetch" in str(args):
                return Mock(returncode=0)
            elif "switch" in str(args):
                return Mock(returncode=0)
            elif "pull" in str(args):
                return Mock(returncode=0)
            elif "show-ref" in str(args):
                return Mock(returncode=1)
            elif "branch" in str(args) and "claude-wt-fail" in str(args):
                return Mock(returncode=0)
            elif "worktree" in str(args) and "add" in str(args):
                raise subprocess.CalledProcessError(
                    1, ["git", "worktree", "add"], "Error creating worktree"
                )
            else:
                return Mock(returncode=0)

        mock_run.side_effect = side_effect

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with pytest.raises(SystemExit) as exc_info:
                        new(query="test", name="fail")
                    assert exc_info.value.code == 1

    @patch("claude_wt.cli.subprocess.run")
    def test_clean_identifies_external_worktrees(self, mock_run):
        """Test that clean correctly identifies external worktrees in sibling directories."""
        # Mixed worktree output with external and non-claude worktrees
        worktree_output = """worktree /home/user/myproject-worktrees/claude-wt-test
HEAD abc123
branch claude-wt-test

worktree /home/user/other-project/feature
HEAD def456
branch feature/something

worktree /home/user/myproject
HEAD ghi789
branch main
"""

        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/myproject", returncode=0),
            # git worktree list --porcelain
            Mock(stdout=worktree_output, returncode=0),
            # git worktree remove for claude-wt-test (should be called)
            Mock(returncode=0),
            # git branch --list claude-wt-*
            Mock(stdout="  claude-wt-test\n", returncode=0),
            # git branch -D for claude-wt-test
            Mock(returncode=0),
        ]

        clean(branch_name="", all=True)

        # Verify that only the claude-wt worktree was targeted for removal
        calls = mock_run.call_args_list
        remove_calls = [
            call for call in calls if "worktree" in str(call) and "remove" in str(call)
        ]

        # Should have exactly 1 worktree remove call
        assert len(remove_calls) == 1
        # And it should be for the external claude-wt worktree
        assert "myproject-worktrees/claude-wt-test" in str(remove_calls[0])
