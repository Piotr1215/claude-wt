"""Tests for path operations in claude-wt."""

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.core import check_gitignore, create_worktree_context, get_worktree_base


class TestPathOperations:
    """Test path-related operations."""

    def test_get_worktree_base_creates_sibling_directory(self):
        """Test that worktree base is a sibling directory to the repo."""
        repo_root = Path("/home/user/projects/my-repo")
        expected = Path("/home/user/projects/my-repo-worktrees")

        result = get_worktree_base(repo_root)

        assert result == expected
        assert result.parent == repo_root.parent
        assert result.name == f"{repo_root.name}-worktrees"

    def test_get_worktree_base_handles_special_characters(self):
        """Test worktree base handles repos with special characters."""
        repo_root = Path("/home/user/projects/my.special-repo_v2")
        expected = Path("/home/user/projects/my.special-repo_v2-worktrees")

        result = get_worktree_base(repo_root)

        assert result == expected

    def test_create_worktree_context_creates_claude_md(self, tmp_path):
        """Test that create_worktree_context creates a proper CLAUDE.md file."""
        wt_path = tmp_path / "test-worktree"
        wt_path.mkdir()
        issue_id = "DOC-123"
        branch_name = "doc-123/fix-stuff"
        repo_root = tmp_path / "main-repo"
        repo_root.mkdir()

        create_worktree_context(wt_path, issue_id, branch_name, repo_root)

        claude_md = wt_path / "CLAUDE.md"
        assert claude_md.exists()

        content = claude_md.read_text()
        assert "WORKTREE" in content  # Updated format uses capitals
        assert "NEVER switch branches" in content  # New safety warning
        assert str(wt_path) in content
        assert str(repo_root) in content
        assert issue_id in content
        assert branch_name in content

    def test_create_worktree_context_overwrites_existing(self, tmp_path):
        """Test that create_worktree_context overwrites existing CLAUDE.md."""
        wt_path = tmp_path / "test-worktree"
        wt_path.mkdir()

        # Create existing CLAUDE.md
        claude_md = wt_path / "CLAUDE.md"
        claude_md.write_text("Old content")

        create_worktree_context(wt_path, "NEW-123", "new-branch", tmp_path)

        content = claude_md.read_text()
        assert "Old content" not in content
        assert "NEW-123" in content

    @patch("claude_wt.cli.Path")
    def test_check_gitignore_finds_pattern_in_local(self, mock_path):
        """Test check_gitignore finds patterns in local .gitignore."""
        mock_repo = Mock()
        mock_gitignore = Mock()
        mock_gitignore.exists.return_value = True
        mock_gitignore.read_text.return_value = """
# Some comment
.claude-wt/worktrees
*.pyc
"""
        mock_repo.__truediv__ = Mock(return_value=mock_gitignore)

        result = check_gitignore(mock_repo)

        assert result is True

    @patch("claude_wt.core.Path")
    def test_check_gitignore_finds_pattern_in_global(self, mock_path):
        """Test check_gitignore finds patterns in global .gitignore."""
        mock_repo = Mock()
        mock_local_gitignore = Mock()
        mock_local_gitignore.exists.return_value = False
        mock_repo.__truediv__ = Mock(return_value=mock_local_gitignore)

        mock_global_gitignore = Mock()
        mock_global_gitignore.exists.return_value = True
        mock_global_gitignore.read_text.return_value = ".claude-wt/*"

        mock_path.home.return_value.__truediv__ = Mock(
            return_value=mock_global_gitignore
        )

        result = check_gitignore(mock_repo)

        assert result is True

    @patch("claude_wt.cli.Path.home")
    @patch("claude_wt.cli.subprocess.run")
    def test_check_gitignore_returns_false_when_not_found(self, mock_run, mock_home):
        """Test check_gitignore returns False when pattern not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_root = Path(tmpdir)
            gitignore = repo_root / ".gitignore"
            gitignore.write_text("*.pyc\n*.log")

            # Mock home directory to avoid checking real global gitignore
            mock_home_dir = Path(tmpdir) / "fake_home"
            mock_home_dir.mkdir()
            mock_home.return_value = mock_home_dir

            # Mock git config to return no custom excludesfile
            mock_run.return_value = Mock(returncode=1, stdout="")

            result = check_gitignore(repo_root)

            assert result is False

    def test_worktree_paths_are_absolute(self):
        """Test that worktree paths are always absolute."""
        repo_root = Path("./my-repo").resolve()
        worktree_base = get_worktree_base(repo_root)

        assert worktree_base.is_absolute()

    def test_worktree_base_preserves_parent_structure(self):
        """Test that worktree base maintains the same parent directory."""
        repo_paths = [
            Path("/home/user/dev/project1"),
            Path("/var/repos/company/service"),
            Path("/opt/code/my-app"),
        ]

        for repo_path in repo_paths:
            worktree_base = get_worktree_base(repo_path)
            assert worktree_base.parent == repo_path.parent
            assert worktree_base.name == f"{repo_path.name}-worktrees"

    def test_create_worktree_context_includes_commands(self, tmp_path):
        """Test that CLAUDE.md includes helpful git commands and warnings."""
        wt_path = tmp_path / "worktree"
        wt_path.mkdir()
        branch_name = "feature/new-stuff"

        create_worktree_context(wt_path, "FEAT-1", branch_name, tmp_path)

        content = (wt_path / "CLAUDE.md").read_text()
        assert "git add" in content
        assert "git commit" in content
        assert f"git push origin {branch_name}" in content
        # Check for new safety warnings
        assert "NEVER switch branches" in content
        assert "git checkout main  # THIS BREAKS EVERYTHING!" in content
        assert "claude-wt switch" in content
