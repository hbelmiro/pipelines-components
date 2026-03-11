#!/usr/bin/env python3
"""CI checks script - stub for TDD (not yet implemented)."""

from __future__ import annotations

import subprocess  # noqa: F401 - needed as patch target for tests
import time  # noqa: F401 - needed as patch target for tests


class ChecksError(Exception):
    """Raised when CI checks fail or time out."""


class GhClient:
    """Wraps subprocess calls to the gh CLI."""

    def remove_label(self, repo: str, pr_number: int, label: str) -> None:
        """Remove a label from a PR."""
        raise NotImplementedError

    def get_check_runs(self, repo: str, head_sha: str) -> dict:
        """Get check runs for a commit."""
        raise NotImplementedError


def should_run_checks(labels: list[str], *, is_member: bool) -> bool:
    """Determine whether CI checks should run based on membership and PR labels."""
    raise NotImplementedError


def reset_label(gh: GhClient, repo: str, pr_number: int) -> None:
    """Remove the ci-passed label from a PR."""
    raise NotImplementedError


def wait_for_checks(
    gh: GhClient,
    repo: str,
    head_sha: str,
    *,
    check_run_id: int,
    delay: int,
    retries: int,
    interval: int,
) -> None:
    """Poll check runs until all pass or retries are exhausted."""
    raise NotImplementedError


def save_pr_payload(output_dir: str, pr_number: int, event_action: str) -> None:
    """Save PR number and event action to files."""
    raise NotImplementedError


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    raise NotImplementedError
