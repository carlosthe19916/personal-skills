from __future__ import annotations

import os
import shlex
from pathlib import Path

from personal_skills.common.remote import (
    detect_provider,
    github_repo_from_url,
    gitlab_identity_from_url,
)

__all__ = [
    "expand_path",
    "worktree_path_for",
    "cd_command_for",
    "repo_label_from_url",
]


def expand_path(path: str) -> str:
    if path == "~":
        return os.path.expanduser("~")
    if path.startswith("~/"):
        return os.path.expanduser(path)
    return path


def worktree_path_for(repo_root: str, number: str) -> str:
    repo_path = Path(repo_root)
    return str(repo_path.parent / f"{repo_path.name}.{number}")


def cd_command_for(path: str) -> str:
    return f"cd {shlex.quote(path)}"


def repo_label_from_url(url: str, repo_root: str) -> str:
    provider = detect_provider(url)
    if provider == "github":
        return github_repo_from_url(url) or Path(repo_root).name
    identity = gitlab_identity_from_url(url)
    if identity:
        return identity[1]
    return Path(repo_root).name
