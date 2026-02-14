"""Tests for file operations (copy_gitignored_files).

Following FIRST principles:
- Fast: No real git operations (mocked/tmp)
- Isolated: Each test independent
- Repeatable: Deterministic outcomes
- Self-Checking: Clear assertions
- Timely: Quick to execute
"""

import pytest

from claude_wt.core import copy_gitignored_files


class TestCopyGitignoredFiles:
    """Test gitignored config file copying behavior."""

    @pytest.fixture
    def mock_repo(self, tmp_path):
        """Create mock repository with config files."""
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        # Create .gitignore listing the files to copy
        (repo_root / ".gitignore").write_text(".envrc\n.mcp.json\nCLAUDE.md\n.claude\n")

        # Create sample config files
        (repo_root / ".envrc").write_text("export TEST=1\n")
        (repo_root / ".mcp.json").write_text('{"test": "data"}\n')
        (repo_root / "CLAUDE.md").write_text("# Test\n")

        # Create .claude directory with a file
        claude_dir = repo_root / ".claude"
        claude_dir.mkdir()
        (claude_dir / "test.txt").write_text("test content\n")

        return repo_root

    @pytest.fixture
    def mock_worktree(self, tmp_path):
        """Create mock worktree path."""
        wt_path = tmp_path / "worktrees" / "test-wt"
        wt_path.mkdir(parents=True)
        return wt_path

    def test_copies_all_config_files(self, mock_repo, mock_worktree):
        """Test that all gitignored config files are copied.

        BEHAVIOR: .envrc, .mcp.json, CLAUDE.md, .claude/ must all be copied
        to ensure consistent development environment.
        """
        # ACT
        copy_gitignored_files(mock_repo, mock_worktree)

        # ASSERT
        assert (mock_worktree / ".envrc").exists(), ".envrc should be copied"
        assert (mock_worktree / ".mcp.json").exists(), ".mcp.json should be copied"
        assert (mock_worktree / "CLAUDE.md").exists(), "CLAUDE.md should be copied"
        assert (mock_worktree / ".claude").exists(), ".claude/ should be copied"
        assert (mock_worktree / ".claude").is_dir(), ".claude should be a directory"

    def test_preserves_file_contents(self, mock_repo, mock_worktree):
        """Test that file contents are preserved during copy.

        BEHAVIOR: Files should be copied with identical contents.
        """
        # ACT
        copy_gitignored_files(mock_repo, mock_worktree)

        # ASSERT
        assert (mock_worktree / ".envrc").read_text() == "export TEST=1\n"
        assert (mock_worktree / ".mcp.json").read_text() == '{"test": "data"}\n'
        assert (mock_worktree / "CLAUDE.md").read_text() == "# Test\n"
        assert (mock_worktree / ".claude" / "test.txt").read_text() == "test content\n"

    def test_handles_missing_files_gracefully(self, tmp_path, mock_worktree):
        """Test that missing source files don't cause failures.

        BEHAVIOR: If config files don't exist in repo, copying should
        continue silently without errors.
        """
        # ARRANGE
        empty_repo = tmp_path / "empty-repo"
        empty_repo.mkdir()

        # ACT - should not raise exception
        copy_gitignored_files(empty_repo, mock_worktree)

        # ASSERT - no files should be created
        assert not (mock_worktree / ".envrc").exists()
        assert not (mock_worktree / ".mcp.json").exists()

    def test_overwrites_existing_claude_directory(self, mock_repo, mock_worktree):
        """Test that existing .claude directory is replaced.

        BEHAVIOR: If .claude already exists in worktree, it should be
        completely replaced with fresh copy from repo.
        """
        # ARRANGE - create existing .claude with different content
        existing_claude = mock_worktree / ".claude"
        existing_claude.mkdir()
        (existing_claude / "old.txt").write_text("old content\n")

        # ACT
        copy_gitignored_files(mock_repo, mock_worktree)

        # ASSERT
        assert not (existing_claude / "old.txt").exists(), "Old files should be removed"
        assert (existing_claude / "test.txt").exists(), "New files should exist"
        assert (existing_claude / "test.txt").read_text() == "test content\n"

    def test_handles_copy_errors_silently(self, tmp_path, mock_worktree):
        """Test that copy errors don't crash worktree creation.

        BEHAVIOR: If individual file copy fails, function continues
        without raising exception.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        (repo_root / ".envrc").write_text("test\n")

        # Make worktree read-only to cause write errors
        mock_worktree.chmod(0o444)

        # ACT - should not raise exception
        try:
            copy_gitignored_files(repo_root, mock_worktree)
        finally:
            # Cleanup - restore permissions
            mock_worktree.chmod(0o755)

        # ASSERT - function completed without exception
        # (no explicit assertion needed, test passes if no exception raised)
