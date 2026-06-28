from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from personal_skills.common.remote import parse_repo_spec
from personal_skills.pr_monitor import fetch
from tests.conftest import MockCliRunner

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("rollup", "expected"),
    [
        ([], None),
        ([{"conclusion": "SUCCESS"}], "SUCCESS"),
        ([{"conclusion": "FAILURE"}], "FAILURE"),
        ([{"status": "IN_PROGRESS"}], "PENDING"),
    ],
)
def test_ci_status_from_rollup(rollup, expected) -> None:
    assert fetch.ci_status_from_rollup(rollup) == expected


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("success", "SUCCESS"),
        ("failed", "FAILURE"),
        ("running", "PENDING"),
        ("canceled", "FAILURE"),
        (None, None),
    ],
)
def test_gitlab_pipeline_status(status, expected) -> None:
    assert fetch.gitlab_pipeline_status(status) == expected


def test_normalize_github_prs_matches_golden() -> None:
    raw = json.loads((FIXTURES / "github_prs_raw.json").read_text())
    normalized = fetch.normalize_github_prs("owner/repo", raw)
    golden = json.loads((FIXTURES / "github_prs_ready.json").read_text())
    assert fetch.apply_filters(normalized, mode="ready") == golden


def test_apply_filters_author_and_mode() -> None:
    items = [
        {"author": "alice", "is_draft": False},
        {"author": "bob", "is_draft": True},
    ]
    assert len(fetch.apply_filters(items, author="alice", mode="all")) == 1
    assert len(fetch.apply_filters(items, mode="wip")) == 1
    assert len(fetch.apply_filters(items, mode="ready")) == 1


def test_fetch_prs_merged_mocked() -> None:
    github_raw = (FIXTURES / "github_prs_raw.json").read_text()
    runner = MockCliRunner(
        which={"gh", "glab"},
        responses={
            ("gh", "auth", "status"): subprocess.CompletedProcess([], 0, "", ""),
            (
                "gh",
                "pr",
                "list",
                "-R",
                "owner/repo",
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                fetch.GITHUB_PR_JSON,
            ): subprocess.CompletedProcess([], 0, github_raw, ""),
        },
    )
    items = fetch.fetch_prs(["github:owner/repo"], mode="ready", runner=runner)
    golden = json.loads((FIXTURES / "github_prs_ready.json").read_text())
    assert items == golden


def test_fetch_gitlab_mrs_merged_mocked() -> None:
    gitlab_raw = (FIXTURES / "gitlab_mrs_raw.json").read_text()
    runner = MockCliRunner(
        which={"glab"},
        responses={
            ("glab", "auth", "status", "--hostname", "gitlab.example.com"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            (
                "glab",
                "mr",
                "list",
                "-R",
                "group/project",
                "--output",
                "json",
                "--per-page",
                "100",
                "--not-draft",
            ): subprocess.CompletedProcess([], 0, gitlab_raw, ""),
        },
    )
    items = fetch.fetch_prs(
        ["gitlab:gitlab.example.com:group/project"],
        mode="ready",
        runner=runner,
    )
    golden = json.loads((FIXTURES / "gitlab_mrs_ready.json").read_text())
    assert items == golden


def test_fetch_github_prs_invalid_json_returns_empty(capsys) -> None:
    runner = MockCliRunner(
        responses={
            (
                "gh",
                "pr",
                "list",
                "-R",
                "owner/repo",
                "--state",
                "open",
                "--limit",
                "100",
                "--json",
                fetch.GITHUB_PR_JSON,
            ): subprocess.CompletedProcess([], 0, "not json", ""),
        },
    )
    items = fetch.fetch_github_prs("owner/repo", runner=runner)
    assert items == []
    assert "invalid JSON" in capsys.readouterr().err


@pytest.mark.live
def test_fetch_prs_live_optional() -> None:
    import os

    if os.environ.get("PR_MONITOR_LIVE") != "1":
        pytest.skip("set PR_MONITOR_LIVE=1 for live fetch")

    items = fetch.fetch_prs(["github:conforma/review-rot"], mode="ready")
    assert isinstance(items, list)
