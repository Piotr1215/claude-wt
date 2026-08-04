"""Tests for tmux integration in claude-wt."""

import os
import sys
from unittest.mock import Mock, patch

import pytest

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.cli import new


class TestTmuxIntegration:
    """Test tmux-related functionality."""

    @patch("claude_wt.cli.subprocess.run")
    @patch("os.environ.get")
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

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        new(query="test", name="tmux-test")

        # Verify that tmux session creation commands were called
        has_session_cmds = [cmd for cmd in tmux_commands if "has-session" in cmd]
        new_session_cmds = [cmd for cmd in tmux_commands if "new-session" in cmd]
        switch_client_cmds = [cmd for cmd in tmux_commands if "switch-client" in cmd]

        assert len(has_session_cmds) > 0
        assert len(new_session_cmds) > 0
        assert len(switch_client_cmds) > 0
        assert any("wt-tmux-test" in str(cmd) for cmd in new_session_cmds)

    @patch("shutil.which")
    @patch("os.environ.get")
    @patch("claude_wt.cli.subprocess.run")
    def test_new_no_tmux_no_window_setting(
        self, mock_run, mock_environ_get, mock_which
    ):
        """Test that 'new' doesn't set tmux window path when not in tmux."""

        # Mock claude executable
        mock_which.return_value = "/usr/bin/claude"

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

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        new(query="test", name="no-tmux-test")

        # Verify that NO tmux commands were run
        assert len(tmux_commands) == 0

    @patch("claude_wt.cli.subprocess.run")
    @patch("os.environ.get")
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

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        new(query="test", name="tmux-window-test")

        # Verify tmux session was created with correct working directory
        new_session_cmds = [cmd for cmd in tmux_commands if "new-session" in cmd]
        assert len(new_session_cmds) > 0
        # Check that the session is created with -c flag for working directory
        assert any("-c" in cmd for cmd in new_session_cmds)
        # Check for centralized worktree path with repo prefix
        assert any(
            "claude-wt-worktrees/repo-claude-wt-tmux-window-test" in str(cmd)
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

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        with patch("builtins.print") as mock_print:
                            new(name="path-test", print_path=True)

                            # Verify only the path was printed
                            mock_print.assert_called_once()
                            printed_path = mock_print.call_args[0][0]
                            # Check for centralized worktree path with repo prefix
                            assert (
                                "claude-wt-worktrees/repo-claude-wt-path-test"
                                in printed_path
                            )

    @patch("claude_wt.worktree.subprocess.run")
    @patch("claude_wt.tmux.subprocess.run")
    @patch("claude_wt.cli.subprocess.run")
    def test_no_pull_flag_skips_pull(
        self, mock_cli_run, mock_tmux_run, mock_worktree_run
    ):
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

        mock_cli_run.side_effect = run_side_effect
        mock_tmux_run.return_value = Mock(returncode=0)
        mock_worktree_run.side_effect = run_side_effect

        with patch("claude_wt.core.check_gitignore", return_value=True):
            with patch("claude_wt.cli.Path.exists", return_value=False):
                with patch("claude_wt.cli.Path.mkdir"):
                    with patch("claude_wt.worktree.create_worktree_context"):
                        with patch(
                            "claude_wt.tmux.shutil.which",
                            return_value="/usr/bin/claude",
                        ):
                            new(name="no-pull-test", pull=False)

        # Verify that git pull and fetch were not called but switch was
        assert not any("git pull" in cmd or " pull " in cmd for cmd in git_commands), (
            f"Git pull found in commands: {git_commands}"
        )
        assert not any(
            "git fetch" in cmd or " fetch " in cmd for cmd in git_commands
        ), f"Git fetch found in commands: {git_commands}"
        assert any("switch" in cmd for cmd in git_commands)


class TestSpawnModelSelection:
    """CLAUDE_SPAWN_MODEL -> --model on the launched claude command.

    __nats_watcher.sh (shortcut-4 model picker) exports CLAUDE_SPAWN_MODEL when
    dispatching a brief-driven worker through claude-wt. _send_claude_command
    turns it into a --model flag that __claude_with_monitor.sh forwards to claude.
    """

    def _sent_command(self, model_env):
        from pathlib import Path

        from claude_wt import tmux_launcher

        sent = {}

        def fake_run(cmd, *a, **k):
            if cmd[:2] == ["tmux", "send-keys"]:
                sent["cmd"] = cmd[4]
            return Mock(returncode=0)

        env = dict(os.environ)
        env.pop("CLAUDE_SPAWN_MODEL", None)
        if model_env is not None:
            env["CLAUDE_SPAWN_MODEL"] = model_env

        with patch.object(tmux_launcher.subprocess, "run", side_effect=fake_run):
            with patch.dict(os.environ, env, clear=True):
                tmux_launcher._send_claude_command(
                    "sess", Path("/tmp/wt"), "/ops-autonomous-worker DOC-1"
                )
        return sent.get("cmd", "")

    def test_no_env_means_no_model_flag(self):
        cmd = self._sent_command(None)
        assert "--model" not in cmd
        assert '--dangerously-skip-permissions -- "/ops-autonomous-worker DOC-1"' in cmd

    def test_model_env_appends_flag_before_prompt(self):
        cmd = self._sent_command("fable")
        assert "--dangerously-skip-permissions --model fable -- " in cmd

    def test_blank_env_is_treated_as_unset(self):
        assert "--model" not in self._sent_command("   ")


class TestAgentRunnerSelection:
    """Codex reuses the shared spawn shell while Claude stays unchanged."""

    def test_codex_uses_shared_spawn_contract(self):
        from pathlib import Path

        from claude_wt import tmux_launcher

        calls = []

        def fake_run(cmd, *args, **kwargs):
            calls.append(cmd)
            return Mock(returncode=0)

        env = {
            "AGENT_RUNNER": "codex",
            "AGENT_SPAWN_MODEL": "gpt-5.6-sol",
        }
        with patch.object(tmux_launcher.subprocess, "run", side_effect=fake_run):
            with patch.dict(os.environ, env, clear=True):
                tmux_launcher.launch_claude_in_tmux(
                    "vcluster-docs-DOC-123",
                    Path("/tmp/worktree"),
                    "/ops-autonomous-worker DOC-123",
                    detached=True,
                )

        spawn = next(
            cmd for cmd in calls if "__spawn_agent.sh" in " ".join(map(str, cmd))
        )
        assert spawn[spawn.index("--runner") + 1] == "codex"
        assert spawn[spawn.index("--model") + 1] == "gpt-5.6-sol"
        assert spawn[spawn.index("--name") + 1] == "vcluster-docs-DOC-123"
        assert spawn[spawn.index("--cwd") + 1] == "/tmp/worktree"
        prompt = spawn[spawn.index("--prompt") + 1]
        assert "Work autonomously on Linear issue DOC-123" in prompt
        assert "/ops-autonomous-worker" not in prompt

    def test_unknown_runner_is_rejected(self):
        from pathlib import Path

        from claude_wt import tmux_launcher

        with patch.dict(os.environ, {"AGENT_RUNNER": "other"}, clear=True):
            with pytest.raises(ValueError, match="AGENT_RUNNER"):
                tmux_launcher.launch_claude_in_tmux(
                    "session", Path("/tmp/worktree"), "task", detached=True
                )
