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


def remote_url(
    repo_root: str,
    *,
    remote_name: str = "origin",
    runner: CliRunner | None = None,
) -> str:
    runner = runner or get_runner()
    result = runner.run(
        ["git", "-C", repo_root, "remote", "get-url", remote_name],
        check=False,
    )
    if result.returncode != 0:
        raise CliError(f"git remote '{remote_name}' not found in {repo_root}")
    url = result.stdout.strip()
    if not url:
        raise CliError(f"git remote '{remote_name}' has no URL in {repo_root}")
    return url


def resolve_provider_context(
    repo_root: str,
    *,
    remote_name: str = "origin",
    url: str | None = None,
    runner: CliRunner | None = None,
) -> ProviderContext:
    runner = runner or get_runner()
    if url is None:
        url = remote_url(repo_root, remote_name=remote_name, runner=runner)

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
