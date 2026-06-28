from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

from personal_skills.common.errors import CliError

Provider = Literal["github", "gitlab", "unknown"]


@dataclass(frozen=True)
class ParsedCheckoutArg:
    kind: Literal["number", "github", "gitlab"]
    number: str
    github_repo: str | None = None
    gitlab_host: str | None = None
    gitlab_path: str | None = None


@dataclass(frozen=True)
class ProviderContext:
    provider: Literal["github", "gitlab"]
    gitlab_host: str = "gitlab.com"


def normalize_gitlab_host(host: str) -> str:
    host = re.sub(r"^https?://", "", host)
    host = host.rstrip("/")
    if "/" in host:
        host = host.split("/", 1)[0]
    return host


def looks_like_hostname(candidate: str) -> bool:
    return "." in candidate or candidate == "gitlab.com"


def detect_provider(url: str) -> Provider:
    lowered = url.lower()

    if re.search(r"(^|[/@])github\.com[:/]", lowered) or lowered.startswith("git@github.com:"):
        return "github"

    ssh = re.match(r"^git@([^:]+):", lowered)
    if ssh:
        host = ssh.group(1)
        if "github" in host:
            return "github"
        if "gitlab" in host:
            return "gitlab"

    https = re.match(r"^https?://([^/]+)/", lowered)
    if https:
        host = https.group(1)
        if "github" in host:
            return "github"
        if "gitlab" in host:
            return "gitlab"

    if github_repo_from_url(url):
        return "github"
    if gitlab_identity_from_url(url):
        return "gitlab"

    return "unknown"


def github_repo_from_url(url: str) -> str | None:
    patterns = [
        r"github\.com[:/]([^/]+/[^/.]+)(?:\.git)?$",
        r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?",
        r"^git@([^:]+):([^/]+/[^/]+?)(?:\.git)?$",
        r"^https?://[^/]*github[^/]*/([^/]+/[^/]+?)(?:\.git)?/?$",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if not match:
            continue
        if pattern.startswith(r"^git@"):
            if "github" not in match.group(1).lower():
                continue
            return match.group(2).removesuffix(".git")
        if pattern == patterns[1]:
            return f"{match.group(1)}/{match.group(2)}"
        return match.group(1).removesuffix(".git")
    return None


def gitlab_identity_from_url(url: str) -> tuple[str, str] | None:
    ssh = re.match(r"^git@([^:]+):(.+?)(?:\.git)?$", url)
    if ssh:
        return normalize_gitlab_host(ssh.group(1)), ssh.group(2).removesuffix(".git")

    https = re.match(r"^https?://([^/]+)/(.+?)(?:\.git)?/?$", url)
    if https:
        return normalize_gitlab_host(https.group(1)), https.group(2).removesuffix(".git")

    return None


def gitlab_host_from_url(url: str) -> str:
    identity = gitlab_identity_from_url(url)
    if identity is None:
        raise ValueError(f"could not parse GitLab host from: {url}")
    return identity[0]


def parse_checkout_arg(arg: str) -> ParsedCheckoutArg:
    if re.fullmatch(r"[0-9]+", arg):
        return ParsedCheckoutArg(kind="number", number=arg)

    github_patterns = [
        r"^https?://[^/]*github[^/]*/([^/]+/[^/]+)/pull/([0-9]+)",
        r"github\.com/([^/]+/[^/]+)/pull/([0-9]+)",
    ]
    for pattern in github_patterns:
        match = re.search(pattern, arg)
        if match:
            return ParsedCheckoutArg(
                kind="github",
                number=match.group(2),
                github_repo=match.group(1).removesuffix(".git"),
            )

    gitlab_match = re.match(r"^https?://([^/]+)/(.+)/-/merge_requests/([0-9]+)", arg)
    if gitlab_match:
        return ParsedCheckoutArg(
            kind="gitlab",
            number=gitlab_match.group(3),
            gitlab_host=normalize_gitlab_host(gitlab_match.group(1)),
            gitlab_path=gitlab_match.group(2).removesuffix(".git"),
        )

    raise CliError(f"expected a PR/MR number or full GitHub/GitLab URL, got: {arg}")


def local_branch_name(provider: Literal["github", "gitlab"], number: str) -> str:
    return f"pr-{number}" if provider == "github" else f"mr-{number}"


def parse_repo_spec(spec: str, default_gitlab_host: str = "gitlab.com") -> tuple[str, str, str]:
    """Return (provider, host, path) where host is empty for GitHub."""
    if spec.startswith("github:"):
        return "github", "", spec.removeprefix("github:")

    if spec.startswith("gitlab:"):
        rest = spec.removeprefix("gitlab:")
        if ":" in rest:
            candidate_host, candidate_path = rest.split(":", 1)
            if looks_like_hostname(candidate_host) and candidate_path:
                return "gitlab", normalize_gitlab_host(candidate_host), candidate_path
        return "gitlab", normalize_gitlab_host(default_gitlab_host), rest

    return "github", "", spec
