from __future__ import annotations

import subprocess
from io import StringIO
from unittest.mock import patch

import pytest

from personal_skills.common.errors import CliError
from personal_skills.common.remote import parse_checkout_arg
from personal_skills.pr_checkout import __main__ as pr_checkout_main
from personal_skills.pr_monitor import __main__ as pr_monitor_main


def test_pr_checkout_help() -> None:
    stderr = StringIO()
    with patch("sys.stderr", stderr):
        code = pr_checkout_main.main(["--help"])
    assert code == 1
    assert "my-app.123" in stderr.getvalue()


def test_pr_checkout_invalid_target(tmp_path, monkeypatch) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", str(repo)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(repo), "remote", "add", "origin", "https://github.com/o/r.git"],
        check=True,
    )
    monkeypatch.chdir(repo)
    stderr = StringIO()
    with patch("sys.stderr", stderr):
        code = pr_checkout_main.main(["checkout", "not-a-valid-target"])
    assert code == 1
    assert "expected a PR/MR number" in stderr.getvalue()


def test_pr_monitor_requires_repo() -> None:
    stderr = StringIO()
    with patch("sys.stderr", stderr):
        code = pr_monitor_main.main(["--ready"])
    assert code == 1
    assert "at least one repository is required" in stderr.getvalue()


def test_parse_checkout_arg_invalid_raises_cli_error() -> None:
    with pytest.raises(CliError, match="expected a PR/MR number"):
        parse_checkout_arg("not-a-url")
