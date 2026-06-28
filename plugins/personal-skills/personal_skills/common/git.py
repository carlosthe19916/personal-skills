from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from personal_skills.common.cli_runner import CliRunner, get_runner
from personal_skills.common.errors import CliError
from personal_skills.common.remote import (
    ProviderContext,
    detect_provider,
    gitlab_host_from_url,
    gitlab_identity_from_url,
    github_repo_from_url,
)


def expand_path(path: str) -> str:
    if path == "~":
        return os.path.expanduser("~")
    if path.startswith("~/"):
        return os.path.expanduser(path)
    return path


def resolve_repo_root(base: str = ".", *, runner: CliRunner | None = None) -> str:
    runner = runner or get_runner()
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
    url = remote_url(repo_root, runner=runner)
    if not url:
        raise CliError(f"no git remote configured in {repo_root}")

    provider = detect_provider(url)
    if provider == "unknown":
        raise CliError(f"remote must be GitHub or GitLab (got: {url})")

    if provider == "gitlab":
        try:
            host = gitlab_host_from_url(url)
        except ValueError as exc:
            raise CliError(str(exc)) from exc
        return ProviderContext(provider="gitlab", gitlab_host=host)
    return ProviderContext(provider="github")


def worktree_path_for(repo_root: str, number: str) -> str:
    repo_path = Path(repo_root)
    return str(repo_path.parent / f"{repo_path.name}.{number}")


def cd_command_for(path: str) -> str:
    import shlex

    return f"cd {shlex.quote(path)}"


@dataclass
class WorktreeEntry:
    path: str
    branch: str
    head: str


def parse_worktree_porcelain(output: str) -> list[WorktreeEntry]:
    entries: list[WorktreeEntry] = []
    current_path = ""
    current_branch = ""
    current_head = ""

    def flush() -> None:
        nonlocal current_path, current_branch, current_head
        if current_path:
            entries.append(
                WorktreeEntry(
                    path=current_path,
                    branch=current_branch,
                    head=current_head,
                )
            )
        current_path = ""
        current_branch = ""
        current_head = ""

    for line in output.splitlines():
        if line.startswith("worktree "):
            flush()
            current_path = line.removeprefix("worktree ")
        elif line.startswith("branch "):
            current_branch = line.removeprefix("branch ").removeprefix("refs/heads/")
        elif line.startswith("HEAD "):
            current_head = line.removeprefix("HEAD ")
        elif line == "":
            flush()
    flush()
    return entries


def worktree_registered(
    repo_root: str, wt_path: str, *, runner: CliRunner | None = None
) -> bool:
    runner = runner or get_runner()
    result = runner.run(
        ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
        check=False,
    )
    if result.returncode != 0:
        return False
    for entry in parse_worktree_porcelain(result.stdout):
        if entry.path == wt_path:
            return True
    return False


def _read_gitdir_path(wt_path: str) -> Path | None:
    git_file = Path(wt_path) / ".git"
    if not git_file.is_file():
        return None
    lines = git_file.read_text(encoding="utf-8").splitlines()
    if not lines or not lines[0].startswith("gitdir:"):
        return None
    gitdir = lines[0].removeprefix("gitdir:").strip()
    if not gitdir:
        return None
    return Path(wt_path) / gitdir if not os.path.isabs(gitdir) else Path(gitdir)


def _gitdir_belongs_to_repo(repo_root: str, wt_path: str) -> bool:
    gitdir = _read_gitdir_path(wt_path)
    if gitdir is None:
        return False
    try:
        repo_git = (Path(repo_root) / ".git").resolve()
        return gitdir.resolve().is_relative_to(repo_git)
    except (OSError, ValueError):
        return False


def is_managed_worktree_path(
    repo_root: str, wt_path: str, *, runner: CliRunner | None = None
) -> bool:
    if worktree_registered(repo_root, wt_path, runner=runner):
        return True
    return _gitdir_belongs_to_repo(repo_root, wt_path)


def repo_label_from_url(url: str, repo_root: str) -> str:
    provider = detect_provider(url)
    if provider == "github":
        return github_repo_from_url(url) or Path(repo_root).name
    identity = gitlab_identity_from_url(url)
    if identity:
        return identity[1]
    return Path(repo_root).name
