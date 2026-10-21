"""Every new worktree starts from the freshly fetched remote default branch.

Real git against throwaway repos: a bare origin whose default is ``trunk`` (a
hardcoded ``origin/main`` would miss it), a clone parked on another branch, and
a commit pushed to origin after the clone so only a real fetch sees it.
"""

import subprocess
from unittest.mock import patch

import pytest

from claude_wt.core import (
    BaseResolutionError,
    create_worktree_context,
    fast_forward_to_origin,
    fresh_default_base,
)
from claude_wt.linear import handle_linear_issue

pytestmark = pytest.mark.real_base

ENV = {
    "GIT_AUTHOR_NAME": "t",
    "GIT_AUTHOR_EMAIL": "t@t",
    "GIT_COMMITTER_NAME": "t",
    "GIT_COMMITTER_EMAIL": "t@t",
}


def git(repo, *args):
    import os

    out = subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        env={**os.environ, **ENV},
    )
    return out.stdout.strip()


@pytest.fixture
def clone(tmp_path):
    """Clone of a ``trunk``-default origin, behind origin by one commit."""
    origin = tmp_path / "origin.git"
    subprocess.run(
        ["git", "init", "-q", "--bare", "-b", "trunk", str(origin)], check=True
    )
    seed = tmp_path / "seed"
    subprocess.run(["git", "clone", "-q", str(origin), str(seed)], capture_output=True)
    git(seed, "checkout", "-q", "-b", "trunk")
    git(seed, "commit", "-q", "--allow-empty", "-m", "base")
    git(seed, "push", "-q", "origin", "trunk")
    repo = tmp_path / "repo"
    subprocess.run(["git", "clone", "-q", str(origin), str(repo)], check=True)
    # Main checkout parked on another task's branch.
    git(repo, "checkout", "-q", "-b", "other-task")
    git(seed, "commit", "-q", "--allow-empty", "-m", "after-clone")
    git(seed, "push", "-q", "origin", "trunk")
    return repo, git(seed, "rev-parse", "HEAD")


def test_non_main_default_resolved_from_remote(clone):
    repo, _ = clone
    assert fresh_default_base(repo) == "origin/trunk"


def test_stale_local_default_is_fetched(clone):
    repo, tip = clone
    assert git(repo, "rev-parse", "origin/trunk") != tip
    base = fresh_default_base(repo)
    assert git(repo, "rev-parse", base) == tip


def test_stale_origin_head_is_not_trusted(clone):
    repo, _ = clone
    git(repo, "update-ref", "refs/remotes/origin/stale", "origin/trunk")
    git(repo, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/stale")
    assert fresh_default_base(repo) == "origin/trunk"


def test_fetch_failure_raises(clone, tmp_path):
    repo, _ = clone
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    with pytest.raises(BaseResolutionError, match="fetch origin failed"):
        fresh_default_base(repo)


def _run_linear(repo, tmp_path):
    base = tmp_path / "worktrees"
    base.mkdir()
    with (
        patch("claude_wt.linear.resolve_repo_path", return_value=repo),
        patch("claude_wt.linear.get_worktree_base", return_value=base),
        patch("claude_wt.linear.create_worktree_context"),
        patch("claude_wt.linear.copy_gitignored_files"),
        patch("claude_wt.linear.install_branch_protection_hook"),
    ):
        with pytest.raises(SystemExit) as exc:
            handle_linear_issue("DEVOPS-9", repo_path=str(repo), interactive=False)
    return exc.value.code, base


def test_linear_dispatch_branches_from_remote_default_tip(clone, tmp_path):
    repo, tip = clone
    code, base = _run_linear(repo, tmp_path)
    assert code == 0
    (wt,) = list(base.iterdir())
    assert git(wt, "rev-parse", "HEAD") == tip
    assert git(wt, "rev-list", "--count", f"{tip}..HEAD") == "0"


def test_linear_dispatch_aborts_when_fetch_fails(clone, tmp_path):
    repo, _ = clone
    git(repo, "remote", "set-url", "origin", str(tmp_path / "gone.git"))
    code, base = _run_linear(repo, tmp_path)
    assert code == 1
    assert list(base.iterdir()) == []
    assert "DEVOPS-9".lower() not in git(repo, "branch", "--list", "devops-9/*")


def _pr_worktree(clone, tmp_path):
    """Worktree on a local pr branch that lags origin/<branch> by one commit."""
    repo, _ = clone
    seed = tmp_path / "seed"
    git(seed, "checkout", "-q", "-b", "pr-branch")
    git(seed, "push", "-q", "origin", "pr-branch")
    git(repo, "fetch", "-q", "origin")
    git(repo, "branch", "--track", "pr-branch", "origin/pr-branch")
    git(seed, "commit", "-q", "--allow-empty", "-m", "pr-new")
    git(seed, "push", "-q", "origin", "pr-branch")
    git(repo, "fetch", "-q", "origin")
    wt = tmp_path / "pr-wt"
    git(repo, "worktree", "add", "-q", str(wt), "pr-branch")
    return wt, git(seed, "rev-parse", "HEAD")


def test_pr_worktree_fast_forwards_to_fresh_branch(clone, tmp_path):
    wt, tip = _pr_worktree(clone, tmp_path)
    fast_forward_to_origin(wt, "pr-branch")
    assert git(wt, "rev-parse", "HEAD") == tip


def test_pr_worktree_diverged_branch_left_alone(clone, tmp_path):
    wt, tip = _pr_worktree(clone, tmp_path)
    git(wt, "commit", "-q", "--allow-empty", "-m", "local-work")
    mine = git(wt, "rev-parse", "HEAD")
    fast_forward_to_origin(wt, "pr-branch")
    assert git(wt, "rev-parse", "HEAD") == mine


def test_tracked_claude_md_is_not_overwritten(clone):
    repo, _ = clone
    (repo / "CLAUDE.md").write_text("repo rules\n")
    git(repo, "add", "CLAUDE.md")
    git(repo, "commit", "-q", "-m", "claude md")
    create_worktree_context(repo, "DEVOPS-9", "b", repo)
    assert (repo / "CLAUDE.md").read_text() == "repo rules\n"
    assert git(repo, "status", "--porcelain") == ""
