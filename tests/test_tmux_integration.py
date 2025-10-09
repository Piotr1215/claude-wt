"""Tests for tmux integration in claude-wt."""

import os
import sys
from unittest.mock import Mock, patch

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.cli import new


class TestTmuxIntegration:
    """Test tmux-related functionality."""

    @patch("claude_wt.cli.subprocess.run")
    @patch("claude_wt.cli.os.environ.get")
    def test_new_creates_tmux_session(self, mock_environ, mock_run):
        """Test that 'new' creates a tmux session when in tmux."""
        # Setup environment to simulate being in tmux
        mock_environ.return_value = "tmux_session_id"

        # Track tmux commands
        tmux_commands = []

        def run_side_effect(*args, **kwargs):
            # Capture tmux commands
            if args[0][0] == "tmux":
                tmux_commands.append(args[0])
                if "has-session" in args[0]:
                    return Mock(returncode=1)  # Session doesn't exist
                return Mock(returncode=0)
            # Handle git commands
            if "rev-parse" in str(args):
                return Mock(stdout="/home/user/repo", returncode=0)
            elif "--show-current" in str(args):
                return Mock(stdout="main", returncode=0)
            elif "show-ref" in str(args):
                return Mock(returncode=1)
            else:
                return Mock(returncode=0)

        mock_run.side_effect = run_side_effect

        with patch("claude_wt.cli.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.cli.create_worktree_context"):
                        new(query="test", name="tmux-test")

        # Verify that tmux session creation commands were called
        has_session_cmds = [cmd for cmd in tmux_commands if "has-session" in cmd]
        new_session_cmds = [cmd for cmd in tmux_commands if "new-session" in cmd]
        switch_client_cmds = [cmd for cmd in tmux_commands if "switch-client" in cmd]

        assert len(has_session_cmds) > 0
        assert len(new_session_cmds) > 0
        assert len(switch_client_cmds) > 0
        assert any("wt-tmux-test" in str(cmd) for cmd in new_session_cmds)

    @patch("os.environ.get")
    @patch("claude_wt.cli.subprocess.run")
    def test_new_no_tmux_no_window_setting(self, mock_run, mock_environ_get):
        """Test that 'new' doesn't set tmux window path when not in tmux."""

        # Setup environment to simulate NOT being in tmux
        def env_side_effect(key, default=None):
            if key == "TMUX":
                return None  # Not in tmux
            elif key == "TERM":
                return "xterm"  # Provide a terminal type for Rich
            return default

        mock_environ_get.side_effect = env_side_effect

        # Track tmux commands
        tmux_commands = []

        def run_side_effect(*args, **kwargs):
            # Capture tmux commands
            if args[0][0] == "tmux":
                tmux_commands.append(args[0])
                return Mock(returncode=0)
            # Handle git commands
            if "rev-parse" in str(args):
                return Mock(stdout="/home/user/repo", returncode=0)
            elif "--show-current" in str(args):
                return Mock(stdout="main", returncode=0)
            elif "show-ref" in str(args):
                return Mock(returncode=1)
            else:
                return Mock(returncode=0)

        mock_run.side_effect = run_side_effect

        with patch("claude_wt.cli.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.cli.create_worktree_context"):
                        new(query="test", name="no-tmux-test")

        # Verify that NO tmux commands were run
        assert len(tmux_commands) == 0

    @patch("claude_wt.cli.subprocess.run")
    @patch("claude_wt.cli.os.environ.get")
    def test_tmux_session_created_with_worktree_path(self, mock_environ, mock_run):
        """Test that tmux session is created with worktree path as working directory."""
        # Setup environment to simulate being in tmux
        mock_environ.return_value = "tmux_session_id"

        # Track tmux commands
        tmux_commands = []

        def run_side_effect(*args, **kwargs):
            # Capture tmux commands
            if args[0][0] == "tmux":
                tmux_commands.append(args[0])
                if "has-session" in args[0]:
                    return Mock(returncode=1)  # Session doesn't exist
                return Mock(returncode=0)
            # Handle git commands
            if "rev-parse" in str(args):
                return Mock(stdout="/home/user/repo", returncode=0)
            elif "--show-current" in str(args):
                return Mock(stdout="main", returncode=0)
            elif "show-ref" in str(args):
                return Mock(returncode=1)
            else:
                return Mock(returncode=0)

        mock_run.side_effect = run_side_effect

        with patch("claude_wt.cli.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.cli.create_worktree_context"):
                        new(query="test", name="tmux-window-test")

        # Verify tmux session was created with correct working directory
        new_session_cmds = [cmd for cmd in tmux_commands if "new-session" in cmd]
        assert len(new_session_cmds) > 0
        # Check that the session is created with -c flag for working directory
        assert any("-c" in cmd for cmd in new_session_cmds)
        assert any(
            "/home/user/repo-worktrees/claude-wt-tmux-window-test" in str(cmd)
            for cmd in new_session_cmds
        )

    @patch("claude_wt.cli.subprocess.run")
    def test_print_path_flag_outputs_path_only(self, mock_run):
        """Test that --print-path outputs only the worktree path."""
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
        ]

        with patch("claude_wt.cli.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.cli.create_worktree_context"):
                        with patch("builtins.print") as mock_print:
                            new(name="path-test", print_path=True)

                            # Verify only the path was printed
                            mock_print.assert_called_once()
                            printed_path = mock_print.call_args[0][0]
                            assert (
                                "/home/user/repo-worktrees/claude-wt-path-test"
                                in printed_path
                            )

    @patch("claude_wt.cli.subprocess.run")
    def test_no_pull_flag_skips_pull(self, mock_run):
        """Test that --no-pull flag skips the pull operation."""
        # Track git commands
        git_commands = []

        def run_side_effect(*args, **kwargs):
            # Capture git commands
            if "git" in args[0][0]:
                git_commands.append(" ".join(args[0]))

            # Handle git commands
            if "rev-parse" in str(args):
                return Mock(stdout="/home/user/repo", returncode=0)
            elif "--show-current" in str(args):
                return Mock(stdout="main", returncode=0)
            elif "show-ref" in str(args):
                return Mock(returncode=1)
            elif "switch" in str(args):
                # Always return success for switch
                return Mock(returncode=0)
            else:
                return Mock(returncode=0, stdout="")

        mock_run.side_effect = run_side_effect

        with patch("claude_wt.cli.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.cli.create_worktree_context"):
                        new(name="no-pull-test", no_pull=True)

        # Verify that git pull and fetch were not called but switch was
        assert not any("git pull" in cmd or " pull " in cmd for cmd in git_commands), (
            f"Git pull found in commands: {git_commands}"
        )
        assert not any(
            "git fetch" in cmd or " fetch " in cmd for cmd in git_commands
        ), f"Git fetch found in commands: {git_commands}"
        assert any("switch" in cmd for cmd in git_commands)
