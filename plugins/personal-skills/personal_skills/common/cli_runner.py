from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence


class CliRunner:
    """Subprocess wrapper for git/gh/glab (mockable in tests)."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

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
        merged_env: dict[str, str] | None = None
        if env is not None:
            merged_env = os.environ.copy()
            merged_env.update(env)
        return subprocess.run(
            list(args),
            cwd=cwd,
            env=merged_env,
            check=check,
            capture_output=capture_output,
            text=text,
        )


_default_runner = CliRunner()


def get_runner() -> CliRunner:
    return _default_runner
