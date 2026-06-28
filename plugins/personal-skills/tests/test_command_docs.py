from __future__ import annotations

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
