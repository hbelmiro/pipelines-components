#!/usr/bin/env python3
"""Unit tests for ci_checks.py script."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, call, patch

import pytest

from ..ci_checks import (
    ChecksError,
    GhClient,
    main,
    reset_label,
    should_run_checks,
    wait_for_checks,
)


def _make_check_run(check_id: int, name: str, status: str, conclusion: str | None = None) -> dict:
    """Build a fake check run dict matching the GitHub API shape."""
    run = {"id": check_id, "name": name, "status": status}
    if conclusion is not None:
        run["conclusion"] = conclusion
    return run


def _api_response(*check_runs: dict) -> str:
    """Wrap check runs in the GitHub API list response envelope."""
    return json.dumps({"total_count": len(check_runs), "check_runs": list(check_runs)})


# ---------------------------------------------------------------------------
# should_run_checks
# ---------------------------------------------------------------------------


class TestShouldRunChecks:
    """Test the should_run_checks function (pure membership + label logic)."""

    def test_member_pr(self):
        """Member PR -- CI should always run."""
        assert should_run_checks([], is_member=True) is True

    def test_non_member_pr_not_yet_approved(self):
        """Non-member PR awaiting approval (needs-ok-to-test) -- CI should NOT run."""
        assert should_run_checks(["needs-ok-to-test"], is_member=False) is False

    def test_non_member_pr_approved_by_maintainer(self):
        """Non-member PR approved (needs-ok-to-test removed, ok-to-test added) -- CI should run."""
        assert should_run_checks(["ok-to-test"], is_member=False) is True

    def test_non_member_pr_no_trust_labels(self):
        """Non-member PR with no trust labels -- CI should NOT run (strict)."""
        assert should_run_checks([], is_member=False) is False

    def test_non_member_pr_unrelated_labels_only(self):
        """Non-member PR with only unrelated labels -- CI should NOT run."""
        assert should_run_checks(["bug", "enhancement"], is_member=False) is False

    def test_member_pr_with_needs_ok_to_test(self):
        """Member PR with needs-ok-to-test (shouldn't happen) -- CI should still run."""
        assert should_run_checks(["needs-ok-to-test"], is_member=True) is True

    def test_member_pr_with_ok_to_test(self):
        """Member PR with ok-to-test (shouldn't happen) -- CI should still run."""
        assert should_run_checks(["ok-to-test"], is_member=True) is True

    def test_member_pr_with_unrelated_labels(self):
        """Member PR with only unrelated labels -- CI should still run."""
        assert should_run_checks(["bug", "enhancement"], is_member=True) is True


# ---------------------------------------------------------------------------
# reset_label
# ---------------------------------------------------------------------------


class FakeGhClient(GhClient):
    """A fake GhClient that tracks label state and check run responses."""

    def __init__(
        self,
        labels: set[str] | None = None,
        check_runs_responses: list[dict] | None = None,
    ) -> None:
        """Initialize with optional label state and check run responses."""
        self.labels = labels if labels is not None else set()
        self._check_runs_responses = list(check_runs_responses or [])
        self._poll_count = 0

    def remove_label(self, repo: str, pr_number: int, label: str) -> None:
        """Remove a label from the tracked set."""
        self.labels.discard(label)

    def get_check_runs(self, repo: str, head_sha: str) -> dict:
        """Return the next canned check runs response."""
        if self._poll_count < len(self._check_runs_responses):
            response = self._check_runs_responses[self._poll_count]
        else:
            response = self._check_runs_responses[-1]
        self._poll_count += 1
        return response


class TestResetLabel:
    """Test the reset_label function."""

    def test_removes_ci_passed_label(self):
        """PR has ci-passed label -- it gets removed."""
        gh = FakeGhClient(labels={"ci-passed", "bug"})
        reset_label(gh, "kubeflow/pipelines-components", 42, ["ci-passed", "bug"])
        assert "ci-passed" not in gh.labels
        assert "bug" in gh.labels

    def test_label_not_present_skips_removal(self):
        """PR does not have ci-passed label -- remove_label is not called."""
        gh = MagicMock(spec=GhClient)
        reset_label(gh, "kubeflow/pipelines-components", 42, ["bug"])
        gh.remove_label.assert_not_called()

    def test_api_unreachable_propagates_error(self):
        """Network/auth errors should propagate to the caller."""
        gh = MagicMock(spec=GhClient)
        gh.remove_label.side_effect = RuntimeError("connection refused")
        with pytest.raises(RuntimeError, match="connection refused"):
            reset_label(gh, "kubeflow/pipelines-components", 42, ["ci-passed"])


# ---------------------------------------------------------------------------
# wait_for_checks
# ---------------------------------------------------------------------------


class TestWaitForChecks:
    """Test the wait_for_checks function."""

    @pytest.fixture(autouse=True)
    def _no_sleep(self):
        """Prevent actual sleeping during polling tests."""
        with patch("ci_checks.ci_checks.time.sleep") as self.mock_sleep:
            yield

    def test_all_checks_pass_on_first_poll(self):
        """All checks completed and passed on first poll."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
                _make_check_run(101, "test", "completed", "success"),
            )
        )
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_pending_then_pass_on_retry(self):
        """Some checks pending on first poll, all pass on second poll."""
        gh = MagicMock(spec=GhClient)
        pending_response = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
                _make_check_run(101, "test", "in_progress"),
            )
        )
        success_response = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
                _make_check_run(101, "test", "completed", "success"),
            )
        )
        gh.get_check_runs.side_effect = [pending_response, success_response]
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_check_fails(self):
        """A check fails -- should raise ChecksError."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
                _make_check_run(101, "test", "completed", "failure"),
            )
        )
        with pytest.raises(ChecksError):
            wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_multiple_checks_fail(self):
        """Multiple checks fail -- should raise ChecksError."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "failure"),
                _make_check_run(101, "test", "completed", "failure"),
            )
        )
        with pytest.raises(ChecksError):
            wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_excludes_own_check_run_id(self):
        """Own check_run_id is excluded from evaluation; remaining checks pass."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(999, "CI Check", "in_progress"),
                _make_check_run(100, "lint", "completed", "success"),
            )
        )
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_no_other_checks_only_self(self):
        """Only the current check run exists -- should succeed."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(999, "CI Check", "in_progress"),
            )
        )
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_mixed_passing_statuses(self):
        """Mixed success, neutral, and skipped -- all treated as passing."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
                _make_check_run(101, "optional", "completed", "neutral"),
                _make_check_run(102, "conditional", "completed", "skipped"),
            )
        )
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    @pytest.mark.parametrize(
        "conclusion",
        ["cancelled", "timed_out", "action_required", "stale"],
    )
    def test_failure_conclusions(self, conclusion):
        """Non-passing conclusions are treated as failures."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "problematic", "completed", conclusion),
            )
        )
        with pytest.raises(ChecksError):
            wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=3, interval=10)

    def test_respects_delay_before_first_poll(self):
        """Delay is applied before the first poll."""
        gh = MagicMock(spec=GhClient)
        gh.get_check_runs.return_value = json.loads(
            _api_response(
                _make_check_run(100, "lint", "completed", "success"),
            )
        )
        wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=120, retries=3, interval=10)
        assert self.mock_sleep.call_args_list[0] == call(120)

    def test_exhausts_retries_when_pending(self):
        """Checks stay pending through all retries -- should raise ChecksError."""
        gh = MagicMock(spec=GhClient)
        pending_response = json.loads(
            _api_response(
                _make_check_run(100, "slow-test", "in_progress"),
            )
        )
        gh.get_check_runs.return_value = pending_response
        with pytest.raises(ChecksError):
            wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=2, interval=5)
        assert gh.get_check_runs.call_count == 2

    def test_empty_check_runs_retries_then_fails(self):
        """No checks registered yet -- retries, eventually fails."""
        gh = MagicMock(spec=GhClient)
        empty_response = json.loads(_api_response())
        gh.get_check_runs.return_value = empty_response
        with pytest.raises(ChecksError):
            wait_for_checks(gh, "owner/repo", "abc123", check_run_id=999, delay=0, retries=2, interval=5)
        assert gh.get_check_runs.call_count == 2


# ---------------------------------------------------------------------------
# GhClient
# ---------------------------------------------------------------------------


class TestGhClient:
    """Test the GhClient class subprocess construction."""

    @patch("ci_checks.ci_checks.subprocess.run")
    def test_remove_label_builds_correct_command(self, mock_run):
        """remove_label calls gh pr edit with correct arguments."""
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0)
        client = GhClient()
        client.remove_label("owner/repo", 42, "ci-passed")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["gh", "pr", "edit", "42", "--remove-label", "ci-passed", "--repo", "owner/repo"]

    @patch("ci_checks.ci_checks.subprocess.run")
    def test_get_check_runs_builds_correct_command(self, mock_run):
        """get_check_runs calls gh api with correct endpoint."""
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=_api_response())
        client = GhClient()
        client.get_check_runs("owner/repo", "abc123")
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd == ["gh", "api", "repos/owner/repo/commits/abc123/check-runs"]


# ---------------------------------------------------------------------------
# CLI integration
# ---------------------------------------------------------------------------


class TestCLIIntegration:
    """Test the main() CLI entry point."""

    _ALL_PASS = [
        json.loads(_api_response(_make_check_run(100, "lint", "completed", "success"))),
    ]

    _CHECK_FAILURE = [
        json.loads(_api_response(_make_check_run(100, "test", "completed", "failure"))),
    ]

    def test_missing_required_args_exits_with_error(self):
        """Missing required arguments should cause a non-zero exit."""
        with pytest.raises(SystemExit) as exc_info:
            main([])
        assert exc_info.value.code != 0

    @patch("ci_checks.ci_checks.GhClient")
    def test_synchronize_event_full_flow(self, mock_gh_client_cls, tmp_path):
        """Synchronize event (member): ci-passed removed, checks pass, payload saved."""
        fake = FakeGhClient(labels={"ci-passed"}, check_runs_responses=self._ALL_PASS)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "synchronize",
                "--labels",
                "ci-passed",
                "--is-member",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" not in fake.labels
        assert Path(output_dir, "pr_number").read_text().strip() == "10"
        assert Path(output_dir, "event_action").read_text().strip() == "synchronize"

    @patch("ci_checks.ci_checks.GhClient")
    def test_reopened_event_removes_ci_passed(self, mock_gh_client_cls, tmp_path):
        """Reopened event (member): ci-passed label is removed."""
        fake = FakeGhClient(labels={"ci-passed"}, check_runs_responses=self._ALL_PASS)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "reopened",
                "--labels",
                "ci-passed",
                "--is-member",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" not in fake.labels

    @patch("ci_checks.ci_checks.GhClient")
    def test_opened_event_preserves_ci_passed(self, mock_gh_client_cls, tmp_path):
        """Opened event (member): ci-passed label is not touched, payload saved."""
        fake = FakeGhClient(labels={"ci-passed"}, check_runs_responses=self._ALL_PASS)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "opened",
                "--labels",
                "",
                "--is-member",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" in fake.labels
        assert Path(output_dir, "pr_number").exists()

    @patch("ci_checks.ci_checks.GhClient")
    def test_labeled_event_preserves_ci_passed(self, mock_gh_client_cls, tmp_path):
        """Labeled event (member): ci-passed label is not touched, payload saved."""
        fake = FakeGhClient(labels={"ci-passed"}, check_runs_responses=self._ALL_PASS)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "labeled",
                "--labels",
                "",
                "--is-member",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" in fake.labels
        assert Path(output_dir, "pr_number").exists()

    @patch("ci_checks.ci_checks.GhClient")
    def test_non_member_unapproved_synchronize_resets_label_but_skips_checks(self, mock_gh_client_cls, tmp_path):
        """Non-member PR (synchronize): ci-passed removed, but no payload saved."""
        fake = FakeGhClient(labels={"ci-passed"})
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "synchronize",
                "--labels",
                "needs-ok-to-test,ci-passed",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" not in fake.labels
        assert not Path(output_dir).exists()

    @patch("ci_checks.ci_checks.GhClient")
    def test_non_member_unapproved_opened_skips_everything(self, mock_gh_client_cls, tmp_path):
        """Non-member PR (opened): labels untouched, no payload saved."""
        fake = FakeGhClient(labels={"ci-passed"})
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "opened",
                "--labels",
                "needs-ok-to-test",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert "ci-passed" in fake.labels
        assert not Path(output_dir).exists()

    @patch("ci_checks.ci_checks.GhClient")
    def test_non_member_approved_runs_checks_and_saves_payload(self, mock_gh_client_cls, tmp_path):
        """Non-member PR approved (ok-to-test): checks run, payload saved."""
        fake = FakeGhClient(check_runs_responses=self._ALL_PASS)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "labeled",
                "--labels",
                "ok-to-test",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result == 0
        assert Path(output_dir, "pr_number").read_text().strip() == "10"

    @patch("ci_checks.ci_checks.GhClient")
    def test_wait_for_checks_failure_prevents_payload_save(self, mock_gh_client_cls, tmp_path):
        """When checks fail, exit non-zero and do NOT save payload."""
        fake = FakeGhClient(check_runs_responses=self._CHECK_FAILURE)
        mock_gh_client_cls.return_value = fake
        output_dir = str(tmp_path / "pr")
        result = main(
            [
                "--pr-number",
                "10",
                "--repo",
                "owner/repo",
                "--event-action",
                "opened",
                "--labels",
                "",
                "--is-member",
                "--check-run-id",
                "999",
                "--head-sha",
                "abc123",
                "--delay",
                "0",
                "--retries",
                "1",
                "--polling-interval",
                "0",
                "--output-dir",
                output_dir,
            ]
        )
        assert result != 0
        assert not Path(output_dir).exists()
