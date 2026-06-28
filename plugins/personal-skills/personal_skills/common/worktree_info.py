from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from personal_skills.common.cli_runner import CliRunner, get_runner

__all__ = [
    "WorktreeEntry",
    "parse_worktree_porcelain",
    "worktree_registered",
    "is_managed_worktree_path",
]


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
