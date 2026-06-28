from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from personal_skills.common.cli_runner import CliRunner, get_runner
from personal_skills.common.errors import CliError
from personal_skills.common.git import (
    cd_command_for,
    is_managed_worktree_path,
    parse_worktree_porcelain,
    remote_url,
    repo_label_from_url,
    resolve_provider_context,
    resolve_repo_root,
    worktree_path_for,
    worktree_registered,
)
from personal_skills.common.remote import (
    ParsedCheckoutArg,
    gitlab_identity_from_url,
    github_repo_from_url,
    local_branch_name,
    parse_checkout_arg,
)


@dataclass
class CheckoutResult:
    repo_root: str
    provider: str
    number: str
    repo: str
    branch: str
    worktree_path: str
    cd_command: str
    created: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "repo_root": self.repo_root,
            "provider": self.provider,
            "number": int(self.number),
            "repo": self.repo,
            "branch": self.branch,
            "worktree_path": self.worktree_path,
            "cd_command": self.cd_command,
            "created": self.created,
        }


def validate_repo_match(
    repo_root: str,
    parsed: ParsedCheckoutArg,
    *,
    runner: CliRunner | None = None,
) -> None:
    origin = remote_url(repo_root, runner=runner)
    if not origin:
        raise CliError(f"no git remote configured in {repo_root}")

    if parsed.kind == "number":
        return

    if parsed.kind == "github":
        actual = github_repo_from_url(origin)
        if actual != parsed.github_repo:
            raise CliError(
                f"URL is for GitHub repo '{parsed.github_repo}' "
                f"but origin is '{actual or 'unknown'}'.\n"
                "Run /pr-checkout from the matching clone."
            )
        return

    identity = gitlab_identity_from_url(origin)
    if identity is None:
        raise CliError(f"could not parse GitLab identity from origin: {origin}")
    host, path = identity
    if host != parsed.gitlab_host or path != parsed.gitlab_path:
        raise CliError(
            f"URL is for GitLab {parsed.gitlab_host}/{parsed.gitlab_path} "
            f"but origin is {host}/{path}."
        )


def preflight_auth(
    provider: str,
    gitlab_host: str = "gitlab.com",
    *,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    if provider == "github":
        if not runner.which("gh"):
            raise CliError("gh CLI is required for GitHub repos but is not installed")
        if runner.run(["gh", "auth", "status"], check=False).returncode != 0:
            raise CliError("gh is not authenticated. Run: gh auth login")
    elif provider == "gitlab":
        if not runner.which("glab"):
            raise CliError("glab CLI is required for GitLab repos but is not installed")
        result = runner.run(
            ["glab", "auth", "status", "--hostname", gitlab_host],
            check=False,
        )
        if result.returncode != 0:
            raise CliError(
                f"glab is not authenticated for {gitlab_host}.\n"
                f"Run: glab auth login --hostname {gitlab_host}"
            )


def _read_head_ref(repo_root: str, *, runner: CliRunner) -> str:
    symbolic = runner.run(
        ["git", "-C", repo_root, "symbolic-ref", "-q", "HEAD"],
        check=False,
    )
    if symbolic.returncode == 0:
        return symbolic.stdout.strip()
    sha = runner.run(["git", "-C", repo_root, "rev-parse", "HEAD"], check=False)
    if sha.returncode != 0:
        raise CliError("could not read current HEAD before provider checkout")
    return sha.stdout.strip()


def _restore_head_ref(repo_root: str, ref: str, *, runner: CliRunner) -> None:
    if ref.startswith("refs/heads/"):
        branch = ref.removeprefix("refs/heads/")
        runner.run(["git", "-C", repo_root, "switch", branch], check=False)
        return
    if ref.startswith("refs/"):
        runner.run(["git", "-C", repo_root, "checkout", "--detach", ref], check=False)
        return
    runner.run(["git", "-C", repo_root, "checkout", "--detach", ref], check=False)


def fetch_pr_branch(
    repo_root: str,
    provider: str,
    number: str,
    local_branch: str,
    *,
    gitlab_host: str = "gitlab.com",
    force: bool = False,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    preflight_auth(provider, gitlab_host, runner=runner)
    previous = _read_head_ref(repo_root, runner=runner)

    if provider == "github":
        args = ["gh", "pr", "checkout", number, "-b", local_branch]
        if force:
            args.append("-f")
        result = runner.run(args, cwd=repo_root, check=False)
        if result.returncode != 0:
            raise CliError(f"gh pr checkout failed for PR #{number}")
    else:
        result = runner.run(
            ["glab", "mr", "checkout", number, "-b", local_branch],
            cwd=repo_root,
            check=False,
            env={"GITLAB_HOST": gitlab_host},
        )
        if result.returncode != 0:
            raise CliError(f"glab mr checkout failed for MR !{number}")

    _restore_head_ref(repo_root, previous, runner=runner)


def delete_local_branch_if_safe(
    repo_root: str,
    branch: str,
    *,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    verify = runner.run(
        ["git", "-C", repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    if verify.returncode != 0:
        return
    deleted = runner.run(
        ["git", "-C", repo_root, "branch", "-D", branch],
        check=False,
    )
    if deleted.returncode != 0:
        raise CliError(f"could not delete branch {branch} (checked out elsewhere?)")


def _number_from_branch(branch: str) -> str | None:
    match = re.fullmatch(r"(?:pr|mr)-([0-9]+)", branch)
    return match.group(1) if match else None


def _run_worktree_remove(
    repo_root: str,
    wt_path: str,
    *,
    runner: CliRunner,
) -> None:
    result = runner.run(
        ["git", "-C", repo_root, "worktree", "remove", "--force", wt_path],
        check=False,
    )
    if result.returncode != 0:
        raise CliError(f"git worktree remove failed for {wt_path}")


def remove_worktree_if_exists(
    repo_root: str,
    wt_path: str,
    branch: str,
    *,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    if worktree_registered(repo_root, wt_path, runner=runner):
        _run_worktree_remove(repo_root, wt_path, runner=runner)
    elif Path(wt_path).exists():
        if is_managed_worktree_path(repo_root, wt_path, runner=runner):
            try:
                _run_worktree_remove(repo_root, wt_path, runner=runner)
            except CliError:
                number = _number_from_branch(branch)
                expected = worktree_path_for(repo_root, number) if number else None
                if expected != wt_path:
                    raise CliError(
                        f"git worktree remove failed for {wt_path} "
                        "(path does not match expected worktree location)"
                    ) from None
                shutil.rmtree(wt_path)
        else:
            raise CliError(
                f"{wt_path} exists but is not a worktree for this repository.\n"
                "Move or remove it manually before retrying."
            )
    delete_local_branch_if_safe(repo_root, branch, runner=runner)


def ensure_branch_available_for_fetch(
    repo_root: str,
    branch: str,
    *,
    force: bool = False,
    runner: CliRunner | None = None,
) -> None:
    runner = runner or get_runner()
    verify = runner.run(
        ["git", "-C", repo_root, "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        check=False,
    )
    if verify.returncode != 0:
        return
    if force:
        delete_local_branch_if_safe(repo_root, branch, runner=runner)
        return
    number = branch.split("-", 1)[-1]
    raise CliError(
        f"branch {branch} already exists.\n"
        f"Use --force to replace it, or: /pr-checkout remove {number}"
    )


def checkout(
    arg: str,
    *,
    force: bool = False,
    repo_path: str = ".",
    runner: CliRunner | None = None,
) -> CheckoutResult:
    runner = runner or get_runner()
    if not arg:
        raise CliError("checkout requires a PR/MR number or URL")

    repo_root = resolve_repo_root(repo_path, runner=runner)
    parsed = parse_checkout_arg(arg)

    if parsed.kind == "number":
        ctx = resolve_provider_context(repo_root, runner=runner)
        provider = ctx.provider
        gitlab_host = ctx.gitlab_host
        validate_repo_match(repo_root, parsed, runner=runner)
    elif parsed.kind == "github":
        provider = "github"
        gitlab_host = "gitlab.com"
        validate_repo_match(repo_root, parsed, runner=runner)
    else:
        provider = "gitlab"
        gitlab_host = parsed.gitlab_host or "gitlab.com"
        validate_repo_match(repo_root, parsed, runner=runner)

    number = parsed.number
    local_branch = local_branch_name(provider, number)
    wt_path = worktree_path_for(repo_root, number)
    url = remote_url(repo_root, runner=runner)

    if Path(wt_path).exists() or worktree_registered(repo_root, wt_path, runner=runner):
        if not force:
            raise CliError(
                f"worktree already exists at {wt_path}\n"
                f"Use --force to remove and recreate, or: /pr-checkout remove {number}"
            )
        remove_worktree_if_exists(repo_root, wt_path, local_branch, runner=runner)

    ensure_branch_available_for_fetch(repo_root, local_branch, force=force, runner=runner)

    fetch_pr_branch(
        repo_root,
        provider,
        number,
        local_branch,
        gitlab_host=gitlab_host,
        force=force,
        runner=runner,
    )

    add_result = runner.run(
        ["git", "-C", repo_root, "worktree", "add", wt_path, local_branch],
        check=False,
    )
    if add_result.returncode != 0:
        runner.run(
            ["git", "-C", repo_root, "branch", "-D", local_branch],
            check=False,
        )
        raise CliError("git worktree add failed")

    cd_command = cd_command_for(wt_path)
    repo_label = repo_label_from_url(url, repo_root)

    return CheckoutResult(
        repo_root=repo_root,
        provider=provider,
        number=number,
        repo=repo_label,
        branch=local_branch,
        worktree_path=wt_path,
        cd_command=cd_command,
    )


def _list_item(
    repo_root: str,
    repo_name: str,
    wt_path: str,
    branch: str,
    head: str,
) -> dict[str, Any] | None:
    parent = str(Path(repo_root).parent)
    expected_prefix = f"{parent}/{repo_name}."
    if not wt_path.startswith(expected_prefix):
        return None

    dir_name = Path(wt_path).name
    pr_match = re.fullmatch(r"pr-([0-9]+)", branch)
    mr_match = re.fullmatch(r"mr-([0-9]+)", branch)

    if pr_match:
        number = int(pr_match.group(1))
        provider = "github"
        prmr = f"PR #{number}"
    elif mr_match:
        number = int(mr_match.group(1))
        provider = "gitlab"
        prmr = f"MR !{number}"
    else:
        suffix = dir_name.removeprefix(f"{repo_name}.")
        if not re.fullmatch(r"[0-9]+", suffix):
            return None
        number = int(suffix)
        provider = "unknown"
        prmr = f"#{number}"

    return {
        "worktree_path": wt_path,
        "directory": dir_name,
        "branch": branch,
        "provider": provider,
        "number": number,
        "prmr": prmr,
        "head": head[:7],
        "cd_command": cd_command_for(wt_path),
    }


def list_worktrees(
    *,
    repo_path: str = ".",
    runner: CliRunner | None = None,
) -> dict[str, Any]:
    runner = runner or get_runner()
    repo_root = resolve_repo_root(repo_path, runner=runner)
    repo_name = Path(repo_root).name

    result = runner.run(
        ["git", "-C", repo_root, "worktree", "list", "--porcelain"],
        check=False,
    )
    if result.returncode != 0:
        raise CliError("git worktree list failed")

    worktrees: list[dict[str, Any]] = []
    for entry in parse_worktree_porcelain(result.stdout):
        item = _list_item(repo_root, repo_name, entry.path, entry.branch, entry.head)
        if item is not None:
            worktrees.append(item)

    return {
        "repo_root": repo_root,
        "repo_name": repo_name,
        "worktrees": worktrees,
    }


def remove(
    number: str,
    *,
    force: bool = False,
    repo_path: str = ".",
    runner: CliRunner | None = None,
) -> dict[str, Any]:
    runner = runner or get_runner()
    if not number:
        raise CliError("remove requires a PR/MR number")
    if not re.fullmatch(r"[0-9]+", number):
        raise CliError("remove target must be a number (e.g. 123)")

    repo_root = resolve_repo_root(repo_path, runner=runner)
    ctx = resolve_provider_context(repo_root, runner=runner)
    local_branch = local_branch_name(ctx.provider, number)
    wt_path = worktree_path_for(repo_root, number)

    has_worktree = worktree_registered(repo_root, wt_path, runner=runner) or Path(
        wt_path
    ).is_dir()
    branch_exists = (
        runner.run(
            [
                "git",
                "-C",
                repo_root,
                "show-ref",
                "--verify",
                "--quiet",
                f"refs/heads/{local_branch}",
            ],
            check=False,
        ).returncode
        == 0
    )

    if not has_worktree and not branch_exists:
        raise CliError(f"no worktree at {wt_path}")

    if has_worktree:
        if Path(wt_path).exists() and not is_managed_worktree_path(
            repo_root, wt_path, runner=runner
        ):
            if not force:
                raise CliError(
                    f"{wt_path} exists but is not a worktree for this repository.\n"
                    "Move or remove it manually before retrying.\n"
                    "(--force does not delete unrelated directories.)"
                )
            raise CliError(
                f"refusing to remove unrelated directory {wt_path}\n"
                "Move or remove it manually; --force cannot override this safety check."
            )
        remove_worktree_if_exists(repo_root, wt_path, local_branch, runner=runner)
    else:
        delete_local_branch_if_safe(repo_root, local_branch, runner=runner)

    return {
        "repo_root": repo_root,
        "number": int(number),
        "branch": local_branch,
        "worktree_path": wt_path,
        "provider": ctx.provider,
        "removed": True,
    }


def emit_json(data: dict[str, Any]) -> str:
    return json.dumps(data, indent=2)
