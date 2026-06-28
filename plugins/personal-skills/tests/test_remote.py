from __future__ import annotations

import pytest

from personal_skills.common.remote import (
    detect_provider,
    github_repo_from_url,
    github_repo_slug_from_remote_url,
    gitlab_identity_from_url,
    gitlab_host_from_url,
    normalize_gitlab_host,
    parse_checkout_arg,
    parse_repo_spec,
    probe_provider,
    resolve_provider_from_url,
)


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("https://gitlab.cee.redhat.com/group", "gitlab.cee.redhat.com"),
        ("gitlab.example.com/", "gitlab.example.com"),
        ("http://gitlab.com/foo", "gitlab.com"),
    ],
)
def test_normalize_gitlab_host(host: str, expected: str) -> None:
    assert normalize_gitlab_host(host) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("git@github.com:org/repo.git", "github"),
        ("https://github.com/org/repo.git", "github"),
        ("git@github.mycompany.com:org/repo.git", "github"),
        ("https://github.mycompany.com/org/repo", "github"),
        ("git@gitlab.example.com:group/project.git", "gitlab"),
        ("https://gitlab.com/group/project", "gitlab"),
        ("git@code.example.com:group/project.git", "unknown"),
        ("https://code.example.com/group/project", "unknown"),
        ("git@code.example.com:group/sub/project.git", "gitlab"),
        ("git@git.acme.com:org/repo.git", "unknown"),
        ("git@bitbucket.org:team/repo.git", "unknown"),
        ("git@codeberg.org:user/repo.git", "unknown"),
    ],
)
def test_detect_provider(url: str, expected: str) -> None:
    assert detect_provider(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.com:owner/repo.git", "owner/repo"),
        ("git@github.mycompany.com:org/repo.git", "org/repo"),
    ],
)
def test_github_repo_from_url(url: str, expected: str) -> None:
    assert github_repo_from_url(url) == expected


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/owner/repo.git", "owner/repo"),
        ("git@github.mycompany.com:org/repo.git", "org/repo"),
        ("git@git.acme.com:org/repo.git", "git.acme.com/org/repo"),
    ],
)
def test_github_repo_slug_from_remote_url(url: str, expected: str) -> None:
    assert github_repo_slug_from_remote_url(url) == expected


@pytest.mark.parametrize(
    ("url", "host", "path"),
    [
        ("git@gitlab.example.com:group/project.git", "gitlab.example.com", "group/project"),
        ("https://gitlab.com/group/project.git", "gitlab.com", "group/project"),
    ],
)
def test_gitlab_identity_from_url(url: str, host: str, path: str) -> None:
    assert gitlab_identity_from_url(url) == (host, path)
    assert gitlab_host_from_url(url) == host


@pytest.mark.parametrize(
    ("arg", "kind", "number", "extra"),
    [
        ("123", "number", "123", {}),
        (
            "https://github.com/owner/repo/pull/42",
            "github",
            "42",
            {"github_repo": "owner/repo"},
        ),
        (
            "https://gitlab.example.com/group/project/-/merge_requests/17",
            "gitlab",
            "17",
            {"gitlab_host": "gitlab.example.com", "gitlab_path": "group/project"},
        ),
    ],
)
def test_parse_checkout_arg(arg: str, kind: str, number: str, extra: dict) -> None:
    parsed = parse_checkout_arg(arg)
    assert parsed.kind == kind
    assert parsed.number == number
    for key, value in extra.items():
        assert getattr(parsed, key) == value


@pytest.mark.parametrize(
    ("spec", "default_host", "expected"),
    [
        ("github:owner/repo", "gitlab.com", ("github", "", "owner/repo")),
        ("owner/repo", "gitlab.com", ("github", "", "owner/repo")),
        (
            "gitlab:gitlab.cee.redhat.com:group/project",
            "gitlab.com",
            ("gitlab", "gitlab.cee.redhat.com", "group/project"),
        ),
        ("gitlab:group/project", "gitlab.com", ("gitlab", "gitlab.com", "group/project")),
    ],
)
def test_parse_repo_spec(spec: str, default_host: str, expected: tuple) -> None:
    assert parse_repo_spec(spec, default_host) == expected


def test_probe_provider_prefers_github_for_ghe() -> None:
    import subprocess

    from tests.conftest import MockCliRunner

    runner = MockCliRunner(
        which={"gh", "glab"},
        responses={
            (
                "gh",
                "repo",
                "view",
                "-R",
                "git.acme.com/org/repo",
                "--json",
                "name",
            ): subprocess.CompletedProcess([], 0, "{}", ""),
        },
    )
    url = "git@git.acme.com:org/repo.git"
    assert detect_provider(url) == "unknown"
    assert probe_provider(url, runner=runner) == "github"


def test_probe_provider_resolves_custom_gitlab_host() -> None:
    import subprocess

    from tests.conftest import MockCliRunner

    runner = MockCliRunner(
        which={"gh", "glab"},
        responses={
            (
                "gh",
                "repo",
                "view",
                "-R",
                "code.example.com/group/project",
                "--json",
                "name",
            ): subprocess.CompletedProcess([], 1, "", ""),
            ("glab", "repo", "view", "group/project"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )
    url = "git@code.example.com:group/project.git"
    assert resolve_provider_from_url(url, runner=runner) == "gitlab"
