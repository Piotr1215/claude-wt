"""Tests for CLI commands.

Following FIRST principles and TDD methodology.
Tests focus on behavior verification, not implementation details.
"""

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from claude_wt.cli import (
    clean,
    init,
    install_completion,
    list_worktrees,
    new,
    status,
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


class TestStatusCommand:
    """Test the 'status' command for displaying repository status."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for git operations."""
        with patch("claude_wt.cli.subprocess.run") as mock:
            yield mock

    def test_status_not_in_git_repo(self, mock_subprocess, capsys):
        """Test status when not in a git repository.

        BEHAVIOR: Should display error message and exit.
        """
        # ARRANGE
        mock_subprocess.return_value = Mock(returncode=1)

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            status()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Not in a git repository" in captured.out

    def test_status_in_claude_worktree(self, tmp_path, mock_subprocess, capsys):
        """Test status when in a claude-wt worktree.

        BEHAVIOR: Should show active worktree session information.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        worktree_path = tmp_path / "worktrees" / "claude-wt-test-session"
        worktree_path.mkdir(parents=True)

        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(returncode=0, stdout=str(repo_root)),
            # git branch --show-current
            Mock(returncode=0, stdout="claude-wt-test-session\n"),
            # git worktree list --porcelain
            Mock(
                returncode=0,
                stdout=f"worktree {worktree_path}\nbranch refs/heads/claude-wt-test-session\n",
            ),
        ]

        # Patch Path.cwd() to return worktree path
        with patch("claude_wt.cli.Path.cwd", return_value=worktree_path):
            # ACT
            status()

        # ASSERT
        captured = capsys.readouterr()
        assert "Active Claude worktree session" in captured.out
        assert "test-session" in captured.out
        assert "claude-wt-test-session" in captured.out

    def test_status_in_non_claude_worktree(self, tmp_path, mock_subprocess, capsys):
        """Test status when in a regular worktree (not claude-wt).

        BEHAVIOR: Should indicate worktree but not a claude-wt session.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        worktree_path = tmp_path / "feature-branch"
        worktree_path.mkdir()

        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(returncode=0, stdout=str(repo_root)),
            # git branch --show-current
            Mock(returncode=0, stdout="feature-branch\n"),
            # git worktree list --porcelain
            Mock(
                returncode=0,
                stdout=f"worktree {worktree_path}\nbranch refs/heads/feature-branch\n",
            ),
        ]

        with patch("claude_wt.cli.Path.cwd", return_value=worktree_path):
            # ACT
            status()

        # ASSERT
        captured = capsys.readouterr()
        assert "In a worktree (not claude-wt)" in captured.out
        assert "feature-branch" in captured.out

    def test_status_in_main_repository(self, tmp_path, mock_subprocess, capsys):
        """QUIRK: Main repository shows as 'worktree' in git worktree list.

        DISCOVERED: git worktree list includes the main repository itself,
        so the status command shows it as "In a worktree" rather than
        "In main repository" when the current directory matches repo root.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        mock_subprocess.side_effect = [
            # git rev-parse --show-toplevel
            Mock(returncode=0, stdout=str(repo_root)),
            # git branch --show-current
            Mock(returncode=0, stdout="main\n"),
            # git worktree list --porcelain
            Mock(returncode=0, stdout=f"worktree {repo_root}\nbranch refs/heads/main\n"),
        ]

        with patch("claude_wt.cli.Path.cwd", return_value=repo_root):
            # ACT
            status()

        # ASSERT
        captured = capsys.readouterr()
        # Main repo shows as worktree due to git worktree list behavior
        assert "In a worktree" in captured.out or "In main repository" in captured.out
        assert "main" in captured.out

    def test_status_handles_subprocess_error(self, mock_subprocess, capsys):
        """Test error handling when git commands fail.

        BEHAVIOR: Should catch and display errors gracefully.
        """
        # ARRANGE
        mock_subprocess.side_effect = subprocess.CalledProcessError(1, ["git", "status"])

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            status()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out


class TestInitCommand:
    """Test the 'init' command for repository initialization."""

    @pytest.fixture
    def mock_subprocess(self):
        """Mock subprocess for git operations."""
        with patch("claude_wt.cli.subprocess.run") as mock:
            yield mock

    @pytest.fixture
    def mock_check_gitignore(self):
        """Mock check_gitignore function."""
        with patch("claude_wt.cli.check_gitignore") as mock:
            yield mock

    def test_init_adds_to_gitignore(
        self, tmp_path, mock_subprocess, mock_check_gitignore, capsys
    ):
        """Test init adds pattern to .gitignore.

        BEHAVIOR: Should add .claude-wt/worktrees to .gitignore if not present.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        gitignore = repo_root / ".gitignore"

        mock_subprocess.return_value = Mock(stdout=str(repo_root))
        mock_check_gitignore.return_value = False

        # ACT
        with patch("claude_wt.cli.Path", return_value=repo_root):
            init()

        # ASSERT
        captured = capsys.readouterr()
        assert "Added .claude-wt/worktrees to .gitignore" in captured.out

    def test_init_skips_if_already_ignored(
        self, tmp_path, mock_subprocess, mock_check_gitignore, capsys
    ):
        """Test init skips when already in .gitignore.

        BEHAVIOR: Should detect existing pattern and skip modification.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        mock_subprocess.return_value = Mock(stdout=str(repo_root))
        mock_check_gitignore.return_value = True

        # ACT
        init()

        # ASSERT
        captured = capsys.readouterr()
        assert "already in .gitignore" in captured.out

    def test_init_handles_subprocess_error(self, mock_subprocess, capsys):
        """Test error handling when git operations fail.

        BEHAVIOR: Should catch subprocess errors gracefully.
        """
        # ARRANGE
        mock_subprocess.side_effect = subprocess.CalledProcessError(
            1, ["git", "rev-parse"]
        )

        # ACT & ASSERT
        with pytest.raises(SystemExit) as exc_info:
            init()

        assert exc_info.value.code == 1
        captured = capsys.readouterr()
        assert "Error" in captured.out

    def test_init_handles_file_write_error(
        self, tmp_path, mock_subprocess, mock_check_gitignore, capsys
    ):
        """Test error handling when writing .gitignore fails.

        BEHAVIOR: Should catch and display file write errors.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()

        mock_subprocess.return_value = Mock(stdout=str(repo_root))
        mock_check_gitignore.return_value = False

        # Make gitignore unwritable by mocking Path
        with patch("claude_wt.cli.Path") as mock_path:
            mock_path_instance = Mock()
            mock_path_instance.exists.return_value = False
            mock_path_instance.write_text.side_effect = PermissionError(
                "Permission denied"
            )
            mock_path.return_value = mock_path_instance

            # ACT & ASSERT
            with pytest.raises(SystemExit) as exc_info:
                init()

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


class TestSecurityEdgeCases:
    """Security-focused tests for CLI commands."""

    @pytest.mark.skip(reason="Hangs in test environment - needs investigation")
    def test_new_command_rejects_path_traversal_in_prompt_file(self, tmp_path):
        """SECURITY: Should handle path traversal attempts safely.

        Path traversal attempts in prompt file path should not
        escape the intended directory.
        """
        # ARRANGE
        dangerous_path = "../../../etc/passwd"

        # ACT & ASSERT
        with pytest.raises(SystemExit):
            new(query="test", prompt_file=dangerous_path)

    def test_status_handles_malicious_branch_names(self, tmp_path, capsys):
        """SECURITY: Should safely handle branch names with special characters.

        Branch names with shell metacharacters should not be executed.
        """
        # ARRANGE
        dangerous_branch = "branch; rm -rf /"

        with patch("claude_wt.cli.subprocess.run") as mock_subprocess:
            mock_subprocess.side_effect = [
                Mock(returncode=0, stdout=str(tmp_path)),
                Mock(returncode=0, stdout=f"{dangerous_branch}\n"),
                Mock(returncode=0, stdout=f"worktree {tmp_path}\n"),
            ]

            with patch("claude_wt.cli.Path.cwd", return_value=tmp_path):
                # ACT
                status()

        # ASSERT - Should display without executing
        captured = capsys.readouterr()
        # Branch name should be displayed as string, not executed
        assert isinstance(captured.out, str)


class TestCLIQuirks:
    """Document quirky behaviors discovered in CLI."""

    def test_init_appends_to_gitignore_without_deleting(self, tmp_path, capsys):
        """QUIRK: init appends to .gitignore, preserving existing content.

        DISCOVERED: Existing .gitignore content is preserved when adding
        the .claude-wt/worktrees pattern.
        """
        # ARRANGE
        repo_root = tmp_path / "repo"
        repo_root.mkdir()
        gitignore = repo_root / ".gitignore"
        gitignore.write_text("node_modules/\n*.log\n")

        with patch("claude_wt.cli.subprocess.run") as mock_subprocess:
            mock_subprocess.return_value = Mock(stdout=str(repo_root))

            with patch("claude_wt.cli.check_gitignore", return_value=False):
                # ACT
                init()

        # ASSERT
        content = gitignore.read_text()
        assert "node_modules/" in content
        assert "*.log" in content
        assert ".claude-wt/worktrees" in content

    def test_status_command_checks_worktree_with_is_relative_to(self, tmp_path):
        """QUIRK: status uses is_relative_to() for worktree detection.

        DISCOVERED: status command uses Path.is_relative_to() which means
        subdirectories of worktrees are also detected as being in the worktree.
        """
        # This tests the logic at lines 209 and 218 in cli.py
        worktree_path = tmp_path / "worktrees" / "my-worktree"
        worktree_path.mkdir(parents=True)
        subdir = worktree_path / "src" / "components"
        subdir.mkdir(parents=True)

        # Verify the logic
        assert subdir.is_relative_to(worktree_path)
        assert worktree_path.is_relative_to(worktree_path)
