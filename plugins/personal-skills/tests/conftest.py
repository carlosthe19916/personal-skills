from __future__ import annotations

import subprocess
from collections.abc import Mapping, Sequence

from personal_skills.common.cli_runner import CliRunner


class MockCliRunner(CliRunner):
    """Records commands and returns canned responses keyed by command prefix."""

    def __init__(
        self,
        responses: dict[tuple[str, ...], subprocess.CompletedProcess[str]] | None = None,
        which: set[str] | None = None,
    ) -> None:
        self.responses = responses or {}
        self.which_commands = which or set()
        self.calls: list[list[str]] = []

    def which(self, name: str) -> str | None:
        if name in self.which_commands:
            return f"/usr/bin/{name}"
        return None

    def run(
        self,
        args: Sequence[str],
        *,
        cwd: str | None = None,
        env: Mapping[str, str] | None = None,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        self.calls.append(list(args))
        key = tuple(args)
        if key in self.responses:
            result = self.responses[key]
            if check and result.returncode != 0:
                raise subprocess.CalledProcessError(
                    result.returncode, list(args), result.stdout, result.stderr
                )
            return result

        for prefix, result in self.responses.items():
            if len(args) >= len(prefix) and tuple(args[: len(prefix)]) == prefix:
                if check and result.returncode != 0:
                    raise subprocess.CalledProcessError(
                        result.returncode, list(args), result.stdout, result.stderr
                    )
                return result

        return subprocess.CompletedProcess(list(args), 1, "", "")
