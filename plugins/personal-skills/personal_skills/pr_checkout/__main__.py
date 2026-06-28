from __future__ import annotations

import argparse
import json
import sys

from personal_skills.common.errors import CliError
from personal_skills.common.paths import expand_path
from personal_skills.pr_checkout import worktree


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pr-checkout",
        description="Create, list, and remove sibling git worktrees for GitHub PRs and GitLab MRs.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    checkout = sub.add_parser("checkout", help="Checkout PR/MR into sibling worktree")
    checkout.add_argument("--force", action="store_true")
    checkout.add_argument("target", help="PR/MR number or URL")

    list_cmd = sub.add_parser("list", help="List PR/MR worktrees")
    list_cmd.add_argument("--path", dest="repo_path", default=".")

    remove = sub.add_parser("remove", help="Remove worktree and branch")
    remove.add_argument("--force", action="store_true")
    remove.add_argument("--path", dest="repo_path", default=".")
    remove.add_argument("number")

    return parser


def usage() -> None:
    print(
        """Usage: pr-checkout checkout [--force] <number-or-url>
       pr-checkout list [--path PATH]
       pr-checkout remove [--path PATH] <number>

Note: remove --force does not delete unrelated directories (safety).

Worktree path: $(dirname repo)/$(basename repo).${NUMBER}
Example: /home/user/git/my-app + 123 -> /home/user/git/my-app.123""",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help"):
        usage()
        return 1 if argv else 0

    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if exc.code is not None else 1

    try:
        if args.command == "checkout":
            result = worktree.checkout(args.target, force=args.force)
            print(
                f"Worktree ready: {result.worktree_path}  (branch {result.branch})\n\n"
                f"  {result.cd_command}",
                file=sys.stderr,
            )
            print(json.dumps(result.to_dict(), indent=2))
        elif args.command == "list":
            data = worktree.list_worktrees(repo_path=expand_path(args.repo_path))
            print(json.dumps(data, indent=2))
        elif args.command == "remove":
            data = worktree.remove(
                args.number,
                force=args.force,
                repo_path=expand_path(args.repo_path),
            )
            print(json.dumps(data, indent=2))
        else:
            usage()
            return 1
    except CliError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return exc.code

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
