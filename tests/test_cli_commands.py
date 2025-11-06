"""Tests for CLI commands.

Following FIRST principles and TDD methodology.
Tests focus on behavior verification, not implementation details.
"""

import subprocess
from unittest.mock import Mock, patch

import pytest

from claude_wt.cli import (
    clean,
    install_completion,
    list_worktrees,
    new,
    switch,
)


class TestNewCommand:
    """Test the 'new' command for creating worktrees."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for git operations."""
        with patch("claude_wt.cli.subprocess.run") as mock:
            yield mock

    @pytest.fixture
    def mock_create_worktree(self):
        """Mock the create_new_worktree function."""
        with patch("claude_wt.cli.create_new_worktree") as mock:
            yield mock

    def test_new_with_prompt_file(self, tmp_path, mock_create_worktree, capsys):
        """Test new command with prompt file parameter.

        BEHAVIOR: Should read prompt from file when --prompt-file provided.
        """
        # ARRANGE
        prompt_file = tmp_path / "prompt.txt"
        prompt_file.write_text("My custom prompt from file")

        # ACT
        new(query="ignored", prompt_file=str(prompt_file))

        # ASSERT
        mock_create_worktree.assert_called_once()
        # First argument should be the file content, not the original query
        assert mock_create_worktree.call_args[0][0] == "My custom prompt from file"
        # Should show message about loading from file
        captured = capsys.readouterr()
        assert "Loaded prompt from" in captured.out

    def test_new_with_missing_prompt_file(self, tmp_path, mock_create_worktree, capsys):
        """Test new command with non-existent prompt file.

        BEHAVIOR: Should exit with error when prompt file doesn't exist.
        """
        # ARRANGE
        missing_file = tmp_path / "nonexistent.txt"

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            new(query="test", prompt_file=str(missing_file))

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out
        assert "not found" in captured.out

    def test_new_handles_subprocess_error(self, mock_create_worktree, capsys):
        """Test error handling when git operations fail.

        BEHAVIOR: Should catch and display subprocess errors gracefully.
        """
        # ARRANGE
        mock_create_worktree.side_effect = subprocess.CalledProcessError(
            1, ["git", "worktree", "add"]
        )

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            new(query="test task")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_new_handles_unexpected_error(self, mock_create_worktree, capsys):
        """Test error handling for unexpected errors.

        BEHAVIOR: Should catch and display unexpected errors gracefully.
        """
        # ARRANGE
        mock_create_worktree.side_effect = RuntimeError("Unexpected error")

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            new(query="test task")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out


class TestCleanCommand:
    """Test the 'clean' command for removing worktrees."""

    @pytest.fixture
    def mock_clean_worktrees(self):
        """Mock the clean_worktrees function."""
        with patch("claude_wt.cli.clean_worktrees") as mock:
            yield mock

    def test_clean_handles_subprocess_error(self, mock_clean_worktrees, capsys):
        """Test error handling when git clean operations fail.

        BEHAVIOR: Should catch subprocess errors and exit gracefully.
        """
        # ARRANGE
        mock_clean_worktrees.side_effect = subprocess.CalledProcessError(
            1, ["git", "worktree", "remove"]
        )

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            clean(branch_name="test-branch")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_clean_handles_unexpected_error(self, mock_clean_worktrees, capsys):
        """Test error handling for unexpected errors.

        BEHAVIOR: Should display unexpected errors gracefully.
        """
        # ARRANGE
        mock_clean_worktrees.side_effect = ValueError("Unexpected issue")

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            clean(branch_name="test-branch")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out


class TestListCommand:
    """Test the 'list' command for displaying worktrees."""

    @pytest.fixture
    def mock_list_worktrees_table(self):
        """Mock the list_worktrees_table function."""
        with patch("claude_wt.cli.list_worktrees_table") as mock:
            yield mock

    def test_list_handles_subprocess_error(self, mock_list_worktrees_table, capsys):
        """Test error handling when listing fails.

        BEHAVIOR: Should catch subprocess errors gracefully.
        """
        # ARRANGE
        mock_list_worktrees_table.side_effect = subprocess.CalledProcessError(
            1, ["git", "worktree", "list"]
        )

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            list_worktrees()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_list_handles_unexpected_error_with_traceback(
        self, mock_list_worktrees_table, capsys
    ):
        """Test error handling shows traceback for unexpected errors.

        BEHAVIOR: Should display traceback for debugging unexpected errors.
        """
        # ARRANGE
        mock_list_worktrees_table.side_effect = RuntimeError("Unexpected error")

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            list_worktrees()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out


class TestSwitchCommand:
    """Test the 'switch' command for switching worktrees."""

    @pytest.fixture
    def mock_switch_worktree(self):
        """Mock the switch_worktree function."""
        with patch("claude_wt.cli.switch_worktree") as mock:
            yield mock

    def test_switch_handles_subprocess_error(self, mock_switch_worktree, capsys):
        """Test error handling when switch fails.

        BEHAVIOR: Should catch subprocess errors gracefully.
        """
        # ARRANGE
        mock_switch_worktree.side_effect = subprocess.CalledProcessError(
            1, ["tmux", "switch-client"]
        )

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            switch()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_switch_handles_unexpected_error(self, mock_switch_worktree, capsys):
        """Test error handling for unexpected errors.

        BEHAVIOR: Should display unexpected errors gracefully.
        """
        # ARRANGE
        mock_switch_worktree.side_effect = ValueError("Unexpected issue")

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            switch()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Unexpected error" in captured.out


class TestInstallCompletionCommand:
    """Test the 'install-completion' command."""

    def test_install_completion_unsupported_shell(self, capsys):
        """Test error when requesting unsupported shell.

        BEHAVIOR: Should reject shells other than zsh with helpful message.
        """
        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            install_completion(shell="bash")

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "bash completions not yet supported" in captured.out
        assert "Currently supported: zsh" in captured.out

    def test_install_completion_zsh_success(self, tmp_path, capsys):
        """Test successful zsh completion installation.

        BEHAVIOR: Should install completion file and show instructions.
        """
        # ARRANGE
        completion_content = "#compdef claude-wt\ntest completion"

        with patch("importlib.resources.files") as mock_files:
            mock_file = Mock()
            mock_file.read_text.return_value = completion_content
            mock_files.return_value.joinpath.return_value = mock_file

            with patch("claude_wt.cli.Path.home", return_value=tmp_path):
                # ACT
                install_completion(shell="zsh")

        # ASSERT
        captured = capsys.readouterr()
        assert "Installed zsh completion" in captured.out
        assert "fpath=(~/.zsh/completions $fpath)" in captured.out
        assert "autoload -Uz compinit" in captured.out

        # Verify file was created
        completion_file = tmp_path / ".zsh" / "completions" / "_claude-wt"
        assert completion_file.exists()
        assert completion_file.read_text() == completion_content

    def test_install_completion_handles_error(self, capsys):
        """Test error handling when installation fails.

        BEHAVIOR: Should show error and manual installation instructions.
        """
        # ARRANGE
        with patch("importlib.resources.files") as mock_files:
            mock_files.side_effect = RuntimeError("File not found")

            # ACT & ASSERT
            with pytest.raises(SystemExit) as exc_info:
                install_completion(shell="zsh")

            assert exc_info.value.code == 1
            captured = capsys.readouterr()
            assert "Error installing completion" in captured.out
            assert "Manual installation" in captured.out
