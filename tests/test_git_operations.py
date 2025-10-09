"""Tests for git operations in claude-wt."""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock, call
import subprocess
import tempfile
import os
import sys

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.cli import (
    get_worktree_base,
    create_worktree_context,
    check_gitignore,
    new,
    resume,
    clean,
    list as list_worktrees
)


class TestGitOperations:
    """Test git-related operations."""

    @patch('claude_wt.cli.subprocess.run')
    def test_new_creates_worktree_with_branch(self, mock_run):
        """Test that 'new' command creates a worktree and branch."""
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
            # Launch Claude script
            Mock(returncode=0),
        ]

        with patch('claude_wt.cli.check_gitignore', return_value=True):
            with patch('claude_wt.cli.Path.exists') as mock_exists:
                mock_exists.return_value = False
                with patch('claude_wt.cli.Path.mkdir'):
                    with patch('claude_wt.cli.create_worktree_context'):
                        # This would normally exit, so we catch the SystemExit
                        new(query="test query", name="test-feature")

        # Verify git commands were called
        calls = mock_run.call_args_list
        assert any("rev-parse" in str(call) for call in calls)
        assert any("worktree" in str(call) and "add" in str(call) for call in calls)

    @patch('claude_wt.cli.subprocess.run')
    def test_resume_finds_existing_worktree(self, mock_run):
        """Test that resume finds and uses existing worktree."""
        worktree_output = """worktree /home/user/repo-worktrees/claude-wt-test
HEAD abc123
branch claude-wt-test

worktree /home/user/repo
HEAD def456
branch main
"""

        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git worktree list --porcelain
            Mock(stdout=worktree_output, returncode=0),
            # Launch Claude script
            Mock(returncode=0),
        ]

        with patch('claude_wt.cli.Path.exists', return_value=True):
            # The resume function launches Claude and returns normally
            resume("test")

        # Verify the Claude script was launched
        calls = mock_run.call_args_list
        assert len(calls) == 3  # rev-parse, worktree list, and Claude launch

    @patch('claude_wt.cli.subprocess.run')
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

        with patch('claude_wt.cli.Path.exists', return_value=True):
            clean(branch_name="test", all=False)

        # Verify both worktree remove and branch delete were called
        calls = mock_run.call_args_list
        assert any("worktree" in str(call) and "remove" in str(call) for call in calls)
        assert any("branch" in str(call) and "-D" in str(call) for call in calls)

    @patch('claude_wt.cli.subprocess.run')
    def test_clean_all_removes_all_claude_worktrees(self, mock_run):
        """Test that clean --all removes all claude-wt worktrees."""
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

    @patch('claude_wt.cli.subprocess.run')
    def test_list_shows_claude_worktrees(self, mock_run):
        """Test that list command shows only claude-wt worktrees."""
        worktree_output = """worktree /home/user/repo-worktrees/claude-wt-test
HEAD abc123
branch claude-wt-test

worktree /home/user/other-branch
HEAD def456
branch feature/other

worktree /home/user/repo
HEAD ghi789
branch main
"""

        mock_run.side_effect = [
            # git rev-parse --show-toplevel
            Mock(stdout="/home/user/repo", returncode=0),
            # git worktree list --porcelain
            Mock(stdout=worktree_output, returncode=0),
        ]

        with patch('claude_wt.cli.Path.exists', return_value=True):
            # This prints to console, so we just verify it doesn't error
            list_worktrees()

        # Verify the git worktree list command was called
        calls = mock_run.call_args_list
        assert any("worktree" in str(call) and "list" in str(call) for call in calls)

    @patch('claude_wt.cli.subprocess.run')
    def test_handles_existing_branch(self, mock_run):
        """Test that new command handles existing branch gracefully."""
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
            # Launch Claude script
            Mock(returncode=0),
        ]

        with patch('claude_wt.cli.check_gitignore', return_value=True):
            with patch('claude_wt.cli.Path.exists', return_value=False):
                with patch('claude_wt.cli.Path.mkdir'):
                    with patch('claude_wt.cli.create_worktree_context'):
                        new(query="test", name="existing")

        # Verify branch creation was skipped (show-ref succeeded)
        calls = mock_run.call_args_list
        branch_create_calls = [call for call in calls if "branch" in str(call) and "claude-wt-existing" in str(call)]
        # Should only be show-ref, not branch creation
        assert len(branch_create_calls) == 0 or "show-ref" in str(branch_create_calls[0])

    @patch('claude_wt.cli.subprocess.run')
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
                raise subprocess.CalledProcessError(1, ["git", "worktree", "add"], "Error creating worktree")
            else:
                return Mock(returncode=0)

        mock_run.side_effect = side_effect

        with patch('claude_wt.cli.check_gitignore', return_value=True):
            with patch('claude_wt.cli.Path.exists', return_value=False):
                with patch('claude_wt.cli.Path.mkdir'):
                    with pytest.raises(subprocess.CalledProcessError):
                        new(query="test", name="fail")

    @patch('claude_wt.cli.subprocess.run')
    def test_init_adds_to_gitignore(self, mock_run):
        """Test that init command adds .claude-wt/worktrees to .gitignore."""
        from claude_wt.cli import init

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)

            # Mock git rev-parse to return our temp dir
            mock_run.return_value = Mock(stdout=str(repo_root), returncode=0)

            with patch('claude_wt.cli.check_gitignore', return_value=False):
                # Create an existing .gitignore
                gitignore = repo_root / ".gitignore"
                gitignore.write_text("*.pyc\n")

                init()

                # Check that .claude-wt/worktrees was added
                content = gitignore.read_text()
                assert ".claude-wt/worktrees" in content
                assert "# Claude worktree management" in content

    @patch('claude_wt.cli.subprocess.run')
    def test_init_skips_if_already_ignored(self, mock_run):
        """Test that init skips if pattern already in gitignore."""
        from claude_wt.cli import init

        mock_run.return_value = Mock(stdout="/home/user/repo", returncode=0)

        with patch('claude_wt.cli.check_gitignore', return_value=True):
            # Should not raise an error, just print success message
            init()

        # No file operations should have occurred
        assert mock_run.call_count == 1  # Only git rev-parse