from __future__ import annotations

import argparse
import json
import sys

from personal_skills.common.errors import CliError
from personal_skills.common.remote import normalize_gitlab_host
from personal_skills.pr_monitor import fetch


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-monitor",
        description="Fetch open PRs/MRs across GitHub and GitLab repos.",
    )
    parser.add_argument("--author", default="")
    parser.add_argument("--gitlab-host", default="gitlab.com")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--include-drafts", "--all", dest="mode", action="store_const", const="all")
    mode.add_argument("--wip", dest="mode", action="store_const", const="wip")
    mode.add_argument("--ready", dest="mode", action="store_const", const="ready")
    parser.set_defaults(mode="ready")
    parser.add_argument("repos", nargs="*", help="github:owner/repo gitlab:HOST:group/project ...")
    return parser


def usage() -> None:
    print(
        """Usage: pr-monitor [--author LOGIN] [--gitlab-host HOST] [--include-drafts | --wip | --ready] \\
  [github:owner/repo | gitlab:HOST:group/project | gitlab:group/project | owner/repo ...]

Repo prefixes:
  github:owner/repo                  GitHub repository
  gitlab:HOST:group/project          GitLab project on a specific instance
  gitlab:group/project               GitLab project (--gitlab-host or gitlab.com)""",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv == ["-h"] or argv == ["--help"]:
        usage()
        return 1 if argv else 0

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1

    if not args.repos:
        print("Error: at least one repository is required", file=sys.stderr)
        usage()
        return 1

    try:
        items = fetch.fetch_prs(
            args.repos,
            author=args.author,
            mode=args.mode,
            default_gitlab_host=normalize_gitlab_host(args.gitlab_host),
        )
        print(json.dumps(items, indent=2))
    except CliError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return exc.code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
