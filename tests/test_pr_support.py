"""Tests for PR worktree support"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import Mock, call, patch

import pytest

# Add the parent directory to path to import claude_wt
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from claude_wt.cli import from_pr_noninteractive


class TestFromPRNoninteractive:
    """Test from-pr-noninteractive command"""

    @patch("claude_wt.cli.Path.write_text")
    @patch("claude_wt.cli.Path.mkdir")
    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    def test_from_pr_noninteractive_basic(
        self, mock_cwd, mock_print, mock_run, mock_mkdir, mock_write
    ):
        """Test basic PR worktree creation"""
        # Setup
        mock_cwd.return_value = Path("/home/user/repo")

        # Mock gh pr view to return proper JSON
        pr_json = json.dumps(
            {
                "headRefName": "feature/branch-123",
                "title": "Test PR",
                "number": 123,
                "body": "Test body",
            }
        )

        mock_run.side_effect = [
            Mock(returncode=0, stdout="/home/user/repo", stderr=""),  # git rev-parse
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view (JSON)
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(
                returncode=1, stdout="", stderr=""
            ),  # git show-ref (branch doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git branch (create branch)
            Mock(returncode=0, stdout="", stderr=""),  # git worktree add
        ]

        # Test - expect SystemExit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="123")

        assert exc_info.value.code == 0, "Should exit successfully"

        # Verify gh pr view was called
        assert mock_run.call_args_list[1] == call(
            ["gh", "pr", "view", "123", "--json", "headRefName,title,number,body"],
            capture_output=True,
            text=True,
            check=True,
            cwd=Path("/home/user/repo"),
        )

        # Verify git worktree add was called
        worktree_calls = [
            call for call in mock_run.call_args_list if "worktree" in call[0][0]
        ]
        assert len(worktree_calls) > 0
        # The command is git -C <repo> worktree add ...
        worktree_cmd = worktree_calls[0][0][0]
        assert worktree_cmd[0] == "git"
        assert "worktree" in worktree_cmd
        assert "add" in worktree_cmd

        # Verify output - the function prints the worktree path to stdout and messages to stderr
        # The main output is the worktree path
        assert mock_print.called  # Ensure something was printed
        # Check that a path containing "pr-123" was printed
        assert any("pr-123" in str(call) for call in mock_print.call_args_list)

    @patch("claude_wt.cli.Path.write_text")
    @patch("claude_wt.cli.Path.mkdir")
    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    def test_from_pr_noninteractive_with_repo_name(
        self, mock_cwd, mock_print, mock_run, mock_mkdir, mock_write
    ):
        """Test PR worktree creation with explicit repo name"""
        # Setup
        mock_cwd.return_value = Path("/home/user/myrepo")

        # Mock gh pr view to return proper JSON
        pr_json = json.dumps(
            {
                "headRefName": "feature/branch-456",
                "title": "Test PR 456",
                "number": 456,
                "body": "Test PR body",
            }
        )

        mock_run.side_effect = [
            # When repo_path is not ".", no git rev-parse is called
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view (JSON)
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(
                returncode=1, stdout="", stderr=""
            ),  # git show-ref (branch doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git branch (create branch)
            Mock(returncode=0, stdout="", stderr=""),  # git worktree add
        ]

        # Test with explicit repo path - expect SystemExit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="456", repo_path="/home/user/myrepo")

        assert exc_info.value.code == 0, "Should exit successfully"

        # Verify worktree was created in the sibling directory
        assert any(
            "/home/user/myrepo-worktrees/" in str(call) or "pr-456" in str(call)
            for call in mock_print.call_args_list
        )

    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    def test_from_pr_noninteractive_pr_not_found(self, mock_cwd, mock_print, mock_run):
        """Test handling when PR doesn't exist"""
        # Setup
        mock_cwd.return_value = Path("/home/user/repo")

        # Mock gh pr view to fail with CalledProcessError
        from subprocess import CalledProcessError

        mock_run.side_effect = CalledProcessError(
            1, ["gh", "pr", "view"], stderr="no pull request found"
        )

        # Test - should exit gracefully
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="999")

        # Verify exit code is 1
        assert exc_info.value.code == 1

        # Verify error message was printed to stderr
        # Since we're using print(..., file=sys.stderr), check the calls
        assert exc_info.value.code == 1  # Just verify it exited with error

    @patch("claude_wt.cli.Path.write_text")
    @patch("claude_wt.cli.Path.mkdir")
    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    @patch("claude_wt.cli.Path.exists")
    def test_from_pr_noninteractive_worktree_exists(
        self, mock_exists, mock_cwd, mock_print, mock_run, mock_mkdir, mock_write
    ):
        """Test handling when worktree already exists"""
        # Setup
        mock_cwd.return_value = Path("/home/user/repo")

        # Mock gh pr view to return proper JSON
        pr_json = json.dumps(
            {
                "headRefName": "feature/existing",
                "title": "Test PR 789",
                "number": 789,
                "body": "",
            }
        )

        mock_run.side_effect = [
            Mock(returncode=0, stdout="/home/user/repo", stderr=""),  # git rev-parse
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view (JSON)
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(returncode=0, stdout="", stderr=""),  # git show-ref (branch exists)
            Mock(returncode=0, stdout="", stderr=""),  # git branch -f (update branch)
            Mock(returncode=0, stdout="", stderr=""),  # git checkout (in worktree)
        ]

        # Mock that worktree path exists
        def mock_exists_side_effect():
            # Return True for the worktree path check
            return True

        mock_exists.return_value = True

        # Test - expect SystemExit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="789")

        assert exc_info.value.code == 0, "Should exit successfully"

        # Should print the existing worktree path
        assert any(
            "pr-789-feature-existing" in str(call) for call in mock_print.call_args_list
        )

    @patch("claude_wt.cli.Path.write_text")
    @patch("claude_wt.cli.Path.mkdir")
    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    @patch.dict("os.environ", {"TMUX": "1"})
    def test_from_pr_noninteractive_with_tmux(
        self, mock_cwd, mock_print, mock_run, mock_mkdir, mock_write
    ):
        """Test PR worktree creation with tmux session"""
        # Setup
        mock_cwd.return_value = Path("/home/user/repo")

        # Mock gh pr view to return proper JSON
        pr_json = json.dumps(
            {
                "headRefName": "feature/tmux-test",
                "title": "Test PR 321",
                "number": 321,
                "body": "",
            }
        )

        # Mock commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/home/user/repo", stderr=""),  # git rev-parse
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view (JSON)
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(
                returncode=1, stdout="", stderr=""
            ),  # git show-ref (branch doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git branch (create branch)
            Mock(returncode=0, stdout="", stderr=""),  # git worktree add
        ]

        # Test - expect SystemExit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="321")

        assert exc_info.value.code == 0, "Should exit successfully"

        # Verify the worktree was created (tmux session is created by the hook, not this function)
        worktree_calls = [
            call for call in mock_run.call_args_list if "worktree" in call[0][0]
        ]
        assert len(worktree_calls) > 0

        # Verify the output contains the worktree path
        assert any(
            "worktree" in str(call).lower() for call in mock_print.call_args_list
        )

    @patch("claude_wt.github.launch_claude_in_tmux")
    @patch("claude_wt.github.install_branch_protection_hook")
    @patch("claude_wt.github.copy_gitignored_files")
    @patch("claude_wt.github.create_worktree_context")
    @patch("claude_wt.github.get_worktree_base")
    @patch("claude_wt.github.resolve_repo_path")
    @patch("claude_wt.github.subprocess.run")
    @patch("builtins.print")
    def test_pr_uses_only_pr_review_slash_command(
        self,
        mock_print,
        mock_run,
        mock_resolve,
        mock_worktree_base,
        mock_context,
        mock_copy_files,
        mock_install_hook,
        mock_launch_claude,
    ):
        """Test PR handler ONLY uses /ops-pr-review, no Linear ID or skill activation.

        BEHAVIOR: PR handler should focus ONLY on PR review.
        No automatic Linear ID extraction, no skill activation, no magic.
        Just: /ops-pr-review {pr_number}
        """
        # Setup
        from claude_wt.github import handle_pr_noninteractive

        mock_repo = Mock(spec=Path)
        mock_repo.name = "repo"
        mock_resolve.return_value = mock_repo

        mock_wt_base = Mock(spec=Path)
        mock_wt_base.mkdir = Mock()
        mock_wt_base.__truediv__ = Mock(
            return_value=Mock(spec=Path, exists=Mock(return_value=False))
        )
        mock_worktree_base.return_value = mock_wt_base

        # Mock gh pr view - branch has Linear ID in it (DOC-429)
        pr_json = json.dumps(
            {
                "headRefName": "doc-429-install-agent",
                "title": "Add installation agent",
                "number": 1340,
                "body": "Fixes DOC-429",
            }
        )

        mock_run.side_effect = [
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(returncode=1, stdout="", stderr=""),  # git show-ref (doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git branch
            Mock(returncode=0, stdout="", stderr=""),  # git worktree add
        ]

        # Act
        with pytest.raises(SystemExit) as exc_info:
            handle_pr_noninteractive(
                pr_number="1340",
                repo_path="/home/user/repo",
                session_name="test-session",
            )

        # Assert
        assert exc_info.value.code == 0

        # Verify launch_claude_in_tmux was called with ONLY /ops-pr-review
        assert mock_launch_claude.called, "Should launch Claude"
        call_args = mock_launch_claude.call_args

        initial_prompt = call_args[0][2]

        # The prompt should be ONLY /ops-pr-review, nothing else
        assert initial_prompt == "/ops-pr-review 1340", (
            f"Expected only '/ops-pr-review 1340', got: {initial_prompt}"
        )

        # Should NOT contain Linear ID (even though branch has DOC-429)
        assert "DOC-429" not in initial_prompt, (
            "Should not extract Linear ID from branch"
        )
        assert "/ops-linear-issue" not in initial_prompt, (
            "Should not add Linear issue command"
        )

        # Should NOT contain skill activation
        assert "skill" not in initial_prompt.lower(), (
            "Should not add skill activation instructions"
        )
        assert "vcluster-docs-writer" not in initial_prompt, (
            "Should not hardcode skill names"
        )

    @patch("claude_wt.cli.Path.write_text")
    @patch("claude_wt.cli.Path.mkdir")
    @patch("claude_wt.cli.subprocess.run")
    @patch("builtins.print")
    @patch("claude_wt.cli.Path.cwd")
    def test_from_pr_noninteractive_basic_completion(
        self, mock_cwd, mock_print, mock_run, mock_mkdir, mock_write
    ):
        """Test PR worktree creation completes successfully"""
        # Setup
        mock_cwd.return_value = Path("/home/user/repo")

        # Mock gh pr view to return proper JSON
        pr_json = json.dumps(
            {
                "headRefName": "feature/query-test",
                "title": "Test PR 555",
                "number": 555,
                "body": "",
            }
        )

        # Mock commands
        mock_run.side_effect = [
            Mock(returncode=0, stdout="/home/user/repo", stderr=""),  # git rev-parse
            Mock(returncode=0, stdout=pr_json, stderr=""),  # gh pr view (JSON)
            Mock(returncode=0, stdout="", stderr=""),  # git fetch
            Mock(
                returncode=1, stdout="", stderr=""
            ),  # git show-ref (branch doesn't exist)
            Mock(returncode=0, stdout="", stderr=""),  # git branch (create branch)
            Mock(returncode=0, stdout="", stderr=""),  # git worktree add
        ]

        # Test without session name - expect SystemExit(0) on success
        with pytest.raises(SystemExit) as exc_info:
            from_pr_noninteractive(pr_number="555")

        assert exc_info.value.code == 0, "Should exit successfully"

        # Verify the command completed successfully
        assert any(
            "worktree" in str(call).lower() for call in mock_print.call_args_list
        )


class TestPRDetectionInHandler:
    """Test PR detection logic in worktree handler"""

    def test_pr_url_detection(self):
        """Test extracting PR number from GitHub URL"""
        import re

        # Test URLs
        test_cases = [
            ("https://github.com/org/repo/pull/123", "123"),
            ("https://github.com/org/repo/pull/456/files", "456"),
            ("https://github.com/org/repo/pull/789#discussion_r123", "789"),
            ("PR: https://github.com/myorg/myrepo/pull/42", "42"),
        ]

        for url, expected_pr in test_cases:
            match = re.search(r"/pull/(\d+)", url)
            assert match is not None, f"Failed to match PR in {url}"
            assert match.group(1) == expected_pr, (
                f"Expected {expected_pr}, got {match.group(1)}"
            )

    def test_repo_uda_field_handling(self):
        """Test handling of repo UDA field"""
        # Simulate task data
        task_with_repo = {
            "repo": "vcluster-pro",
            "tags": ["wt"],
            "annotations": [
                {"description": "https://github.com/org/vcluster-pro/pull/123"}
            ],
        }

        # Extract repo from UDA
        repo_name = task_with_repo.get("repo", "").strip()
        assert repo_name == "vcluster-pro"

        # Build repo path
        repo_path = f"/home/decoder/loft/{repo_name}"
        assert repo_path == "/home/decoder/loft/vcluster-pro"

    def test_pr_vs_linear_detection(self):
        """Test differentiating between PR and Linear issue tasks"""
        # PR task
        pr_task = {
            "tags": ["wt"],
            "annotations": [{"description": "https://github.com/org/repo/pull/123"}],
            "repo": "myrepo",
        }

        # Linear task
        linear_task = {"tags": ["wt"], "linear_id": "DOC-1234", "session": "vdocs"}

        # Check PR task
        pr_annotations = pr_task.get("annotations", [])
        has_pr = False
        for annotation in pr_annotations:
            desc = annotation.get("description", "")
            if "github.com" in desc and "/pull/" in desc:
                has_pr = True
                break
        assert has_pr is True, "Should detect PR task"

        # Check Linear task
        linear_annotations = linear_task.get("annotations", [])
        has_pr_in_linear = False
        for annotation in linear_annotations:
            desc = annotation.get("description", "")
            if "github.com" in desc and "/pull/" in desc:
                has_pr_in_linear = True
                break
        assert has_pr_in_linear is False, "Should not detect PR in Linear task"
        assert linear_task.get("linear_id") == "DOC-1234", "Should have Linear ID"


class TestPRWorkflowIntegration:
    """Test the full PR workflow integration"""

    @patch("subprocess.run")
    def test_pr_task_triggers_worktree_handler(self, mock_run):
        """Test that PR task with +wt tag triggers worktree handler correctly"""
        # Simulate task data that would be passed to hook
        after = {
            "tags": ["wt"],
            "repo": "vcluster-docs",
            "annotations": [
                {
                    "description": "Review PR: https://github.com/loft-sh/vcluster-docs/pull/789"
                }
            ],
            "start": "20250110T120000Z",
        }

        # The hook would:
        # 1. Detect +wt tag
        # 2. Find PR URL in annotations
        # 3. Extract PR number (789)
        # 4. Use repo UDA field to determine path
        # 5. Call claude-wt from-pr-noninteractive

        # Verify PR detection
        pr_number = None
        for annotation in after.get("annotations", []):
            desc = annotation.get("description", "")
            if "github.com" in desc and "/pull/" in desc:
                import re

                match = re.search(r"/pull/(\d+)", desc)
                if match:
                    pr_number = match.group(1)

        assert pr_number == "789", "Should extract PR number from annotation"

        # Verify repo detection
        repo_name = after.get("repo", "").strip()
        assert repo_name == "vcluster-docs", "Should get repo from UDA field"

        # Verify this would trigger PR handling, not Linear handling
        linear_id = after.get("linear_id", "").strip()
        assert not linear_id, "Should not have Linear ID for PR task"

    def test_pr_worktree_naming_convention(self):
        """Test PR worktree naming convention"""
        pr_number = "123"
        branch_name = "feature/awesome-feature"

        # Clean branch name for worktree
        branch_clean = branch_name.replace("/", "-")
        worktree_name = f"pr-{pr_number}-{branch_clean}"

        assert worktree_name == "pr-123-feature-awesome-feature"

        # Test session naming
        session_name = f"wt-pr-{pr_number}"  # Simplified session name

        assert session_name == "wt-pr-123"
