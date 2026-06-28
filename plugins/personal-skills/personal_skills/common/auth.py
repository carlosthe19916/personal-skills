from __future__ import annotations

from personal_skills.common.cli_runner import CliRunner, get_runner
from personal_skills.common.errors import CliError

__all__ = ["check_provider_auth"]


def check_provider_auth(
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
