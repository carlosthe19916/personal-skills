from __future__ import annotations

from personal_skills.common.cli_runner import CliRunner, get_runner
from personal_skills.common.errors import CliError
from personal_skills.common.remote import (
    ProviderContext,
    gitlab_host_from_url,
    resolve_provider_from_url,
)

__all__ = [
    "resolve_repo_root",
    "resolve_fetch_remote",
    "remote_url",
    "resolve_provider_context",
]


def resolve_repo_root(base: str = ".", *, runner: CliRunner | None = None) -> str:
    runner = runner or get_runner()
    from personal_skills.common.paths import expand_path

    expanded = expand_path(base)
    result = runner.run(
        ["git", "-C", expanded, "rev-parse", "--show-toplevel"],
        check=False,
    )
    if result.returncode != 0:
        raise CliError(
            f"not a git repository: {expanded}\n"
            "Run from inside a clone or pass --path to a local repository."
        )
    return result.stdout.strip()


def resolve_fetch_remote(repo_root: str, *, runner: CliRunner | None = None) -> str:
    runner = runner or get_runner()
    origin = runner.run(
        ["git", "-C", repo_root, "remote", "get-url", "origin"],
        check=False,
    )
    if origin.returncode == 0:
        return "origin"

    remotes = runner.run(["git", "-C", repo_root, "remote"], check=False)
    if remotes.returncode == 0 and remotes.stdout.strip():
        return remotes.stdout.strip().splitlines()[0]

    raise CliError(f"no git remote configured in {repo_root}")


def remote_url(repo_root: str, *, runner: CliRunner | None = None) -> str:
    runner = runner or get_runner()
    remote = resolve_fetch_remote(repo_root, runner=runner)
    result = runner.run(
        ["git", "-C", repo_root, "remote", "get-url", remote],
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def resolve_provider_context(
    repo_root: str, *, runner: CliRunner | None = None
) -> ProviderContext:
    runner = runner or get_runner()
    url = remote_url(repo_root, runner=runner)
    if not url:
        raise CliError(f"no git remote configured in {repo_root}")

    provider = resolve_provider_from_url(url, runner=runner)
    if provider == "unknown":
        raise CliError(f"remote must be GitHub or GitLab (got: {url})")

    if provider == "gitlab":
        try:
            host = gitlab_host_from_url(url)
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        return ProviderContext(provider="gitlab", gitlab_host=host)
    return ProviderContext(provider="github")
