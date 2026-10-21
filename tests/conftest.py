"""Shared fixtures.

The unit tests mock ``subprocess.run`` per module, so the real fetch and
``ls-remote`` behind ``fresh_default_base`` must not run in them. The helper is
covered against real repositories in ``test_fresh_base.py``; tests that need the
real thing opt out with ``@pytest.mark.real_base``.
"""

from unittest.mock import patch

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "real_base: run the real fresh_default_base helper"
    )


@pytest.fixture(autouse=True)
def _stub_fresh_base(request):
    if request.node.get_closest_marker("real_base"):
        yield
        return
    with (
        patch("claude_wt.linear.fresh_default_base", return_value="origin/main"),
        patch("claude_wt.worktree.fresh_default_base", return_value="origin/main"),
        patch("claude_wt.worktree.has_origin", return_value=True),
        patch("claude_wt.github.fast_forward_to_origin"),
        patch("claude_wt.core._is_tracked", return_value=False),
    ):
        yield
