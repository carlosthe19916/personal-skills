from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from personal_skills.common.errors import CliError
from personal_skills.common.git import (
    resolve_fetch_remote,
    resolve_provider_context,
)
from personal_skills.common.paths import (
    cd_command_for,
    worktree_path_for,
)
from personal_skills.common.worktree_info import (
    is_managed_worktree_path,
    parse_worktree_porcelain,
)
from personal_skills.common.remote import local_branch_name
from personal_skills.pr_checkout import worktree
from tests.conftest import MockCliRunner


def test_worktree_path_for() -> None:
    assert worktree_path_for("/home/user/git/my-org/my-app", "123") == (
        "/home/user/git/my-org/my-app.123"
    )


def test_cd_command_for_quotes_spaces() -> None:
    assert cd_command_for("/home/user/my app") == "cd '/home/user/my app'"


def test_local_branch_names() -> None:
    assert local_branch_name("github", "7") == "pr-7"
    assert local_branch_name("gitlab", "7") == "mr-7"


def test_parse_worktree_porcelain() -> None:
    output = """worktree /tmp/repo
HEAD abcdef1234567890
branch refs/heads/pr-7

worktree /tmp/repo.7
HEAD 1234567890abcdef
branch refs/heads/pr-7
"""
    entries = parse_worktree_porcelain(output)
    assert len(entries) == 2
    assert entries[1].path == "/tmp/repo.7"
    assert entries[1].branch == "pr-7"


def test_resolve_fetch_remote_prefers_origin(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    runner = MockCliRunner(
        {
            ("git", "-C", str(repo), "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/repo.git", ""
            ),
        }
    )
    assert resolve_fetch_remote(str(repo), runner=runner) == "origin"


def test_list_and_remove_integration(tmp_path: Path) -> None:
    bare = tmp_path / "remote.git"
    repo = tmp_path / "my-app"
    wt = tmp_path / "my-app.7"

    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    subprocess.run(["git", "clone", str(bare), str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "config", "user.email", "test@example.com"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
    subprocess.run(
        [
            "git",
            "-C",
            str(repo),
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--allow-empty",
            "-m",
            "init",
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(repo), "remote", "set-url", "origin", "https://github.com/example/my-app.git"],
        check=True,
    )
    subprocess.run(["git", "-C", str(repo), "branch", "pr-7"], check=True)
    subprocess.run(["git", "-C", str(repo), "worktree", "add", str(wt), "pr-7"], check=True)

    data = worktree.list_worktrees(repo_path=str(repo))
    assert len(data["worktrees"]) == 1
    assert data["worktrees"][0]["number"] == 7

    removed = worktree.remove("7", repo_path=str(repo))
    assert removed["removed"] is True
    assert not wt.exists()


def test_checkout_mocked_fetch_and_add() -> None:
    repo_root = "/home/user/git/my-app"
    calls: list[list[str]] = []

    class RecordingRunner(MockCliRunner):
        def run(self, args, **kwargs):
            calls.append(list(args))
            return super().run(args, **kwargs)

    runner = RecordingRunner(
        which={"gh"},
        responses={
            ("gh", "auth", "status"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, repo_root, ""
            ),
            ("git", "-C", repo_root, "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/my-app.git", ""
            ),
            ("git", "-C", repo_root, "show-ref", "--verify", "--quiet", "refs/heads/pr-123"): subprocess.CompletedProcess(
                [], 1, "", ""
            ),
            ("git", "-C", repo_root, "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, f"worktree {repo_root}\n", ""
            ),
            ("git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"): subprocess.CompletedProcess(
                [], 0, "refs/heads/main", ""
            ),
            ("gh", "pr", "checkout", "123", "-b", "pr-123", "-R", "example/my-app"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "switch", "main"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "worktree", "add", f"{repo_root}.123", "pr-123"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )

    result = worktree.checkout("123", repo_path=repo_root, runner=runner)
    assert result.worktree_path == f"{repo_root}.123"
    assert any("gh pr checkout" in " ".join(c) for c in calls)
    assert any("-R" in c and "example/my-app" in c for c in calls)
    assert any("worktree add" in " ".join(c) for c in calls)
    assert not any(c[:4] == ["git", "-C", repo_root, "fetch"] for c in calls)


def test_remove_refuses_unrelated_directory(tmp_path: Path) -> None:
    repo = tmp_path / "my-app"
    repo.mkdir()
    unrelated = tmp_path / "my-app.9"
    unrelated.mkdir()

    runner = MockCliRunner(
        responses={
            ("git", "-C", str(repo), "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, str(repo), ""
            ),
            ("git", "-C", str(repo), "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/my-app.git", ""
            ),
            ("git", "-C", str(repo), "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            (
                "git",
                "-C",
                str(repo),
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/pr-9",
            ): subprocess.CompletedProcess([], 1, "", ""),
        }
    )

    with pytest.raises(CliError, match="not a worktree"):
        worktree.remove("9", repo_path=str(repo), runner=runner)


def test_remove_force_still_refuses_unrelated_directory(tmp_path: Path) -> None:
    repo = tmp_path / "my-app"
    repo.mkdir()
    unrelated = tmp_path / "my-app.9"
    unrelated.mkdir()

    runner = MockCliRunner(
        responses={
            ("git", "-C", str(repo), "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, str(repo), ""
            ),
            ("git", "-C", str(repo), "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/my-app.git", ""
            ),
            ("git", "-C", str(repo), "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            (
                "git",
                "-C",
                str(repo),
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/pr-9",
            ): subprocess.CompletedProcess([], 1, "", ""),
        }
    )

    with pytest.raises(CliError, match="refusing to remove unrelated"):
        worktree.remove("9", force=True, repo_path=str(repo), runner=runner)


def test_worktree_remove_failure_raises_cli_error() -> None:
    repo_root = "/home/user/git/my-app"
    wt_path = f"{repo_root}.123"
    runner = MockCliRunner(
        responses={
            ("git", "-C", repo_root, "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, repo_root, ""
            ),
            ("git", "-C", repo_root, "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/my-app.git", ""
            ),
            ("git", "-C", repo_root, "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, f"worktree {repo_root}\nworktree {wt_path}\n", ""
            ),
            ("git", "-C", repo_root, "worktree", "remove", "--force", wt_path): subprocess.CompletedProcess(
                [], 1, "", "fatal: error"
            ),
        },
    )

    with pytest.raises(CliError, match="git worktree remove failed"):
        worktree._remove_worktree_if_exists(repo_root, wt_path, "pr-123", runner=runner)


def test_checkout_requires_gh_auth() -> None:
    repo_root = "/home/user/git/my-app"
    runner = MockCliRunner(
        which={"gh"},
        responses={
            ("gh", "auth", "status"): subprocess.CompletedProcess([], 1, "", "not logged in"),
            ("git", "-C", repo_root, "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, repo_root, ""
            ),
            ("git", "-C", repo_root, "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "https://github.com/example/my-app.git", ""
            ),
            ("git", "-C", repo_root, "show-ref", "--verify", "--quiet", "refs/heads/pr-123"): subprocess.CompletedProcess(
                [], 1, "", ""
            ),
            ("git", "-C", repo_root, "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, f"worktree {repo_root}\n", ""
            ),
        },
    )
    with pytest.raises(CliError, match="gh is not authenticated"):
        worktree.checkout("123", repo_path=repo_root, runner=runner)


def test_checkout_gitlab_uses_glab() -> None:
    repo_root = "/home/user/git/my-app"
    calls: list[list[str]] = []

    class RecordingRunner(MockCliRunner):
        def run(self, args, **kwargs):
            calls.append(list(args))
            return super().run(args, **kwargs)

    runner = RecordingRunner(
        which={"glab"},
        responses={
            ("glab", "auth", "status", "--hostname", "code.example.com"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "rev-parse", "--show-toplevel"): subprocess.CompletedProcess(
                [], 0, repo_root, ""
            ),
            ("git", "-C", repo_root, "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "git@code.example.com:group/project.git", ""
            ),
            ("glab", "repo", "view", "group/project"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "show-ref", "--verify", "--quiet", "refs/heads/mr-42"): subprocess.CompletedProcess(
                [], 1, "", ""
            ),
            ("git", "-C", repo_root, "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, f"worktree {repo_root}\n", ""
            ),
            ("git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"): subprocess.CompletedProcess(
                [], 0, "refs/heads/main", ""
            ),
            ("glab", "mr", "checkout", "42", "-b", "mr-42", "-R", "group/project"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "switch", "main"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "worktree", "add", f"{repo_root}.42", "mr-42"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )
    result = worktree.checkout("42", repo_path=repo_root, runner=runner)
    assert result.provider == "gitlab"
    assert any("glab mr checkout" in " ".join(c) for c in calls)
    assert any("-R" in c and "group/project" in c for c in calls)


def test_fetch_pr_branch_restore_head_failure() -> None:
    repo_root = "/home/user/git/my-app"
    calls: list[list[str]] = []

    class RecordingRunner(MockCliRunner):
        def run(self, args, **kwargs):
            calls.append(list(args))
            return super().run(args, **kwargs)

    runner = RecordingRunner(
        which={"gh"},
        responses={
            ("gh", "auth", "status"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"): subprocess.CompletedProcess(
                [], 0, "refs/heads/main", ""
            ),
            (
                "gh",
                "pr",
                "checkout",
                "123",
                "-b",
                "pr-123",
                "-R",
                "example/my-app",
            ): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "switch", "main"): subprocess.CompletedProcess(
                [], 1, "", "failed to switch"
            ),
            (
                "git",
                "-C",
                repo_root,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/pr-123",
            ): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "branch", "-D", "pr-123"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )
    with pytest.raises(CliError, match="could not restore previous HEAD"):
        worktree._fetch_pr_branch(
            repo_root,
            "github",
            "123",
            "pr-123",
            github_repo="example/my-app",
            runner=runner,
        )
    assert any("branch" in " ".join(c) and "-D" in c and "pr-123" in c for c in calls)


def test_fetch_pr_branch_github_force_passes_flag() -> None:
    repo_root = "/home/user/git/my-app"
    calls: list[list[str]] = []

    class RecordingRunner(MockCliRunner):
        def run(self, args, **kwargs):
            calls.append(list(args))
            return super().run(args, **kwargs)

    runner = RecordingRunner(
        which={"gh"},
        responses={
            ("gh", "auth", "status"): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"): subprocess.CompletedProcess(
                [], 0, "refs/heads/main", ""
            ),
            (
                "gh",
                "pr",
                "checkout",
                "123",
                "-b",
                "pr-123",
                "-R",
                "example/my-app",
                "-f",
            ): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "switch", "main"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )
    worktree._fetch_pr_branch(
        repo_root,
        "github",
        "123",
        "pr-123",
        github_repo="example/my-app",
        force=True,
        runner=runner,
    )
    assert any("-f" in c for c in calls)


def test_fetch_pr_branch_gitlab_force_deletes_existing_branch() -> None:
    repo_root = "/home/user/git/my-app"
    calls: list[list[str]] = []

    class RecordingRunner(MockCliRunner):
        def run(self, args, **kwargs):
            calls.append(list(args))
            return super().run(args, **kwargs)

    runner = RecordingRunner(
        which={"glab"},
        responses={
            ("glab", "auth", "status", "--hostname", "code.example.com"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            ("git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"): subprocess.CompletedProcess(
                [], 0, "refs/heads/main", ""
            ),
            (
                "git",
                "-C",
                repo_root,
                "show-ref",
                "--verify",
                "--quiet",
                "refs/heads/mr-42",
            ): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "branch", "-D", "mr-42"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
            (
                "glab",
                "mr",
                "checkout",
                "42",
                "-b",
                "mr-42",
                "-R",
                "group/project",
            ): subprocess.CompletedProcess([], 0, "", ""),
            ("git", "-C", repo_root, "switch", "main"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        },
    )
    worktree._fetch_pr_branch(
        repo_root,
        "gitlab",
        "42",
        "mr-42",
        gitlab_project="group/project",
        gitlab_host="code.example.com",
        force=True,
        runner=runner,
    )
    assert any("branch" in " ".join(c) and "-D" in c for c in calls)


def test_is_managed_worktree_path_rejects_foreign_gitdir(tmp_path: Path) -> None:
    repo = tmp_path / "my-app"
    foreign = tmp_path / "my-app.9"
    other_repo = tmp_path / "other"
    repo.mkdir()
    foreign.mkdir()
    other_repo.mkdir()
    (other_repo / ".git" / "worktrees" / "wt").mkdir(parents=True)
    gitdir_target = other_repo / ".git" / "worktrees" / "wt"
    (foreign / ".git").write_text(f"gitdir: {gitdir_target}\n", encoding="utf-8")

    runner = MockCliRunner(
        responses={
            ("git", "-C", str(repo), "worktree", "list", "--porcelain"): subprocess.CompletedProcess(
                [], 0, "", ""
            ),
        }
    )
    assert not is_managed_worktree_path(str(repo), str(foreign), runner=runner)


def test_resolve_provider_context_custom_gitlab_host(tmp_path: Path) -> None:
    repo = tmp_path / "my-app"
    repo.mkdir()
    runner = MockCliRunner(
        which={"glab"},
        responses={
            ("git", "-C", str(repo), "remote", "get-url", "origin"): subprocess.CompletedProcess(
                [], 0, "git@code.example.com:group/project.git", ""
            ),
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
    ctx = resolve_provider_context(str(repo), runner=runner)
    assert ctx.provider == "gitlab"
    assert ctx.gitlab_host == "code.example.com"
