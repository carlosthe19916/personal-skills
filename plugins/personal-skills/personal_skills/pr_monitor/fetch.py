from __future__ import annotations

import json
import re
import sys
from typing import Any, Literal

from personal_skills.common.auth import check_provider_auth
from personal_skills.common.cli_runner import CliRunner, get_runner
from personal_skills.common.errors import CliError
from personal_skills.common.remote import normalize_gitlab_host, parse_repo_spec

Mode = Literal["all", "wip", "ready"]

GITHUB_PR_JSON = (
    "number,title,url,author,isDraft,updatedAt,createdAt,statusCheckRollup,reviews,labels"
)


def _load_json_array(text: str, *, label: str) -> list[dict[str, Any]] | None:
    try:
        data = json.loads(text or "[]")
    except json.JSONDecodeError:
        print(f"Warning: invalid JSON from {label}", file=sys.stderr)
        return None
    if not isinstance(data, list):
        print(f"Warning: expected JSON array from {label}", file=sys.stderr)
        return None
    return data


def ci_status_from_rollup(rollup: list[dict[str, Any]] | None) -> str | None:
    if not rollup:
        return None

    def conclusion(item: dict[str, Any]) -> str:
        return str(item.get("conclusion") or item.get("state") or "")

    def status(item: dict[str, Any]) -> str:
        return str(item.get("status") or item.get("state") or "")

    if any(re.search(r"FAILURE|ERROR|CANCELLED", conclusion(item), re.I) for item in rollup):
        return "FAILURE"
    if any(
        status(item) == "IN_PROGRESS" or status(item) == "PENDING" for item in rollup
    ):
        return "PENDING"
    if all(re.search(r"SUCCESS|NEUTRAL|SKIPPED", conclusion(item), re.I) for item in rollup):
        return "SUCCESS"
    return "PENDING"


def gitlab_pipeline_status(status: str | None) -> str | None:
    if not status:
        return None
    normalized = status.lower()
    if normalized == "success":
        return "SUCCESS"
    if normalized == "failed":
        return "FAILURE"
    if normalized in ("running", "pending", "created"):
        return "PENDING"
    if normalized in ("canceled", "cancelled"):
        return "FAILURE"
    return status.upper()


def normalize_github_prs(
    repo: str,
    raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in raw:
        author = item.get("author") or {}
        labels = item.get("labels") or []
        reviews = item.get("reviews") or []
        result.append(
            {
                "number": item.get("number"),
                "title": item.get("title"),
                "url": item.get("url"),
                "repo": repo,
                "provider": "github",
                "instance": None,
                "author": author.get("login") or "unknown",
                "is_draft": bool(item.get("isDraft", False)),
                "is_automated": False,
                "created_at": item.get("createdAt"),
                "updated_at": item.get("updatedAt"),
                "ci_status": ci_status_from_rollup(item.get("statusCheckRollup")),
                "reviews": {"count": len(reviews), "has_new_commits": False},
                "labels": [label.get("name") for label in labels if label.get("name")],
                "unresolved_conversations": 0,
            }
        )
    return result


def normalize_gitlab_mrs(
    host: str,
    repo: str,
    raw: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in raw:
        author = item.get("author") or {}
        labels = item.get("labels") or []
        if isinstance(labels, list):
            label_names = [
                label if isinstance(label, str) else label.get("name")
                for label in labels
            ]
            label_names = [name for name in label_names if name]
        else:
            label_names = []

        pipeline = item.get("head_pipeline") or {}
        approved_by = item.get("approved_by") or []

        result.append(
            {
                "number": item.get("iid"),
                "title": item.get("title"),
                "url": item.get("web_url"),
                "repo": repo,
                "provider": "gitlab",
                "instance": host,
                "author": author.get("username") or author.get("name") or "unknown",
                "is_draft": bool(item.get("draft") or item.get("work_in_progress")),
                "is_automated": False,
                "created_at": item.get("created_at"),
                "updated_at": item.get("updated_at"),
                "ci_status": gitlab_pipeline_status(pipeline.get("status")),
                "reviews": {"count": len(approved_by), "has_new_commits": False},
                "labels": label_names,
                "unresolved_conversations": 0,
            }
        )
    return result


def apply_filters(
    items: list[dict[str, Any]],
    *,
    author: str = "",
    mode: Mode = "ready",
) -> list[dict[str, Any]]:
    filtered = items
    if author:
        filtered = [item for item in filtered if item.get("author") == author]
    if mode == "wip":
        filtered = [item for item in filtered if item.get("is_draft")]
    elif mode == "ready":
        filtered = [item for item in filtered if not item.get("is_draft")]
    return filtered


def preflight_auth(
    repos: list[tuple[str, str, str]],
    *,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    need_github = any(provider == "github" for provider, _, _ in repos)
    gitlab_hosts = {host for provider, host, _ in repos if provider == "gitlab"}

    if need_github:
        check_provider_auth("github", runner=runner)
    for host in gitlab_hosts:
        check_provider_auth("gitlab", host, runner=runner)


def fetch_github_prs(
    repo: str,
    *,
    author: str = "",
    runner: CliRunner | None = None,
) -> list[dict[str, Any]]:
    runner = runner or get_runner()
    args = [
        "gh",
        "pr",
        "list",
        "-R",
        repo,
        "--state",
        "open",
        "--limit",
        "100",
        "--json",
        GITHUB_PR_JSON,
    ]
    if author:
        args.extend(["--author", author])
    result = runner.run(
        args,
        check=False,
    )
    if result.returncode != 0:
        print(f"Warning: failed to fetch GitHub PRs for {repo}", file=sys.stderr)
        return []
    raw = _load_json_array(result.stdout, label=f"GitHub PRs for {repo}")
    if raw is None:
        return []
    return normalize_github_prs(repo, raw)


def fetch_gitlab_mrs(
    host: str,
    repo: str,
    *,
    mode: Mode = "ready",
    author: str = "",
    runner: CliRunner | None = None,
) -> list[dict[str, Any]]:
    runner = runner or get_runner()
    args = ["glab", "mr", "list", "-R", repo, "--output", "json", "--per-page", "100"]
    if mode == "ready":
        args.append("--not-draft")
    elif mode == "wip":
        args.append("--draft")
    if author:
        args.extend(["--author", author])

    result = runner.run(args, check=False, env={"GITLAB_HOST": host})
    if result.returncode != 0:
        print(f"Warning: failed to fetch GitLab MRs for {host}/{repo}", file=sys.stderr)
        return []

    raw_text = (result.stdout or "").strip()
    if not raw_text or raw_text in ("[]", "null"):
        return []
    raw = _load_json_array(raw_text, label=f"GitLab MRs for {host}/{repo}")
    if raw is None:
        return []
    return normalize_gitlab_mrs(host, repo, raw)


def fetch_prs(
    repo_specs: list[str],
    *,
    author: str = "",
    mode: Mode = "ready",
    default_gitlab_host: str = "gitlab.com",
    runner: CliRunner | None = None,
) -> list[dict[str, Any]]:
    if not repo_specs:
        raise CliError("at least one repository is required")

    runner = runner or get_runner()
    default_gitlab_host = normalize_gitlab_host(default_gitlab_host)

    repos = [parse_repo_spec(spec, default_gitlab_host) for spec in repo_specs]
    preflight_auth(repos, runner=runner)

    merged: list[dict[str, Any]] = []
    for provider, host, path in repos:
        if provider == "github":
            print(f"Fetching github:{path} ...", file=sys.stderr)
            merged.extend(fetch_github_prs(path, author=author, runner=runner))
        elif provider == "gitlab":
            print(f"Fetching gitlab:{host}:{path} ...", file=sys.stderr)
            merged.extend(
                fetch_gitlab_mrs(
                    host,
                    path,
                    mode=mode,
                    author=author,
                    runner=runner,
                )
            )

    return apply_filters(merged, author=author, mode=mode)
