from __future__ import annotations

import json
import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
COMMANDS_DIR = PLUGIN_ROOT / "commands"
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"


def _parse_frontmatter(text: str) -> dict[str, str]:
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    assert match, "missing YAML frontmatter"
    fields: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def test_every_command_has_frontmatter() -> None:
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        assert meta.get("name"), f"{path.name} missing name"
        assert meta.get("description"), f"{path.name} missing description"


def test_command_frontmatter_description_quoted_when_needed() -> None:
    """Unquoted colons in YAML description break GitHub frontmatter parsing."""
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
        assert match, f"{path.name} missing frontmatter"
        for line in match.group(1).splitlines():
            if not line.startswith("description:"):
                continue
            value = line.removeprefix("description:").strip()
            if ":" in value and not (
                (value.startswith('"') and value.endswith('"'))
                or (value.startswith("'") and value.endswith("'"))
            ):
                raise AssertionError(
                    f"{path.name} description must be quoted (contains ':'): {value!r}"
                )


# Tokens from argument-hint that must appear in the command body (below frontmatter).
_ARGUMENT_HINT_BODY_TOKENS: dict[str, list[str]] = {
    "pr-checkout.md": [
        "help",
        "list",
        "remove",
        "--force",
        "path:DIR",
        "remote:NAME",
        "number",
        "url",
    ],
    "pr-monitor.md": [
        "help",
        "list",
        "sources",
        "setup",
        "init",
        "all",
        "wip",
        "author:",
        "org:",
        "group:",
        "host:",
        "repo:",
    ],
    "npm-vuln-fix.md": [
        "JIRA",
    ],
}


def test_every_command_has_argument_hint() -> None:
    for path in sorted(COMMANDS_DIR.glob("*.md")):
        meta = _parse_frontmatter(path.read_text(encoding="utf-8"))
        assert meta.get("argument-hint"), f"{path.name} missing argument-hint"


def test_argument_hint_tokens_documented_in_body() -> None:
    for filename, tokens in _ARGUMENT_HINT_BODY_TOKENS.items():
        path = COMMANDS_DIR / filename
        text = path.read_text(encoding="utf-8")
        body = text.split("---", 2)[2] if text.startswith("---") else text
        for token in tokens:
            assert token in body, (
                f"{filename} body missing argument-hint token {token!r}"
            )


def test_pr_checkout_argument_hint_matches_command_reference() -> None:
    text = (COMMANDS_DIR / "pr-checkout.md").read_text(encoding="utf-8")
    meta = _parse_frontmatter(text)
    hint = meta["argument-hint"]
    for fragment in ("[remote:NAME]", "[path:DIR]", "[--force]", "[number|url]"):
        assert fragment in hint, f"pr-checkout argument-hint missing {fragment!r}"


def test_wrapper_scripts_exist_and_executable() -> None:
    wrappers = [
        SCRIPTS_DIR / "pr-checkout" / "pr_worktree.sh",
        SCRIPTS_DIR / "pr-monitor" / "fetch_prs.sh",
    ]
    for path in wrappers:
        assert path.is_file(), f"missing wrapper {path}"
        assert path.stat().st_mode & 0o111, f"wrapper not executable: {path}"
        content = path.read_text(encoding="utf-8")
        assert "personal_skills" in content, f"{path.name} must delegate to Python module"


def test_pr_command_docs_reference_wrappers() -> None:
    checkout = (COMMANDS_DIR / "pr-checkout.md").read_text(encoding="utf-8")
    monitor = (COMMANDS_DIR / "pr-monitor.md").read_text(encoding="utf-8")
    assert "pr_worktree.sh" in checkout or "personal_skills.pr_checkout" in checkout
    assert "fetch_prs.sh" in monitor or "personal_skills.pr_monitor" in monitor


def test_version_consistency() -> None:
    from personal_skills import __version__

    plugin_json = json.loads(
        (PLUGIN_ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    pyproject = (PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)
    assert match, "pyproject.toml missing version"

    pyproject_version = match.group(1)
    plugin_version = plugin_json["version"]

    assert __version__ == pyproject_version, (
        f"__init__.py ({__version__}) != pyproject.toml ({pyproject_version})"
    )
    assert __version__ == plugin_version, (
        f"__init__.py ({__version__}) != plugin.json ({plugin_version})"
    )
