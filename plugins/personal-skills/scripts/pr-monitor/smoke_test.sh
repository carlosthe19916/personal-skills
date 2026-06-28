#!/usr/bin/env bash
# Smoke tests for pr-monitor — run before publishing.
# Usage: bash plugins/personal-skills/scripts/pr-monitor/smoke_test.sh
#
# Optional env:
#   PR_MONITOR_LIVE_REPO=github:conforma/review-rot  — live fetch target (public)
#   PR_MONITOR_SKIP_LIVE=1                           — skip network tests

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/pr-monitor/fetch_prs.sh"
EXAMPLE="$ROOT/config/pr-monitor.sources.example.yaml"
LIVE_REPO="${PR_MONITOR_LIVE_REPO:-github:conforma/review-rot}"

pass=0
fail=0

ok() { echo "  ✓ $*"; pass=$((pass + 1)); }
bad() { echo "  ✗ $*"; fail=$((fail + 1)); }

section() { echo; echo "== $* =="; }

section "Static checks"
bash -n "$SCRIPT" && ok "fetch_prs.sh syntax" || bad "fetch_prs.sh syntax"
command -v jq >/dev/null 2>&1 && ok "jq installed" || bad "jq installed"
[[ -f "$EXAMPLE" ]] && ok "example config exists" || bad "example config exists"
[[ -f "$ROOT/commands/pr-monitor.md" ]] && ok "command doc exists" || bad "command doc exists"
[[ -f "$ROOT/commands/pr-checkout.md" ]] && ok "pr-checkout command doc exists" || bad "pr-checkout command doc exists"

section "fetch_prs.sh CLI"
if (bash "$SCRIPT" --help 2>&1 || true) | grep -q "Usage:"; then
  ok "--help"
else
  bad "--help"
fi
if (bash "$SCRIPT" 2>&1 || true) | grep -q "at least one repository"; then
  ok "requires repo arg"
else
  bad "requires repo arg"
fi

section "Repo prefix parsing (via live fetch)"
if [[ "${PR_MONITOR_SKIP_LIVE:-}" == "1" ]]; then
  echo "  (skipped — PR_MONITOR_SKIP_LIVE=1)"
else
  if ! command -v gh >/dev/null 2>&1; then
    echo "  (skipped live — gh not installed)"
  elif ! gh auth status >/dev/null 2>&1; then
    echo "  (skipped live — gh not authenticated; run: gh auth login)"
  else
    count_ready="$(bash "$SCRIPT" --ready "$LIVE_REPO" 2>/dev/null | jq 'length')"
    [[ "$count_ready" -ge 0 ]] && ok "ready mode returns JSON ($count_ready PRs)" || bad "ready mode"

    count_wip="$(bash "$SCRIPT" --wip "$LIVE_REPO" 2>/dev/null | jq 'length')"
    [[ "$count_wip" -ge 0 ]] && ok "wip mode ($count_wip drafts)" || bad "wip mode"

    has_fields="$(bash "$SCRIPT" --ready "$LIVE_REPO" 2>/dev/null | jq '.[0] | has("provider") and has("ci_status") and has("repo")')"
    [[ "$has_fields" == "true" ]] && ok "normalized fields" || bad "normalized fields"
  fi
fi

section "Init bootstrap (temp config)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/pr-monitor"
cp "$EXAMPLE" "$TMP/pr-monitor/sources.yaml"
[[ -f "$TMP/pr-monitor/sources.yaml" ]] && ok "template copy" || bad "template copy"
grep -q 'my-github-org' "$TMP/pr-monitor/sources.yaml" && ok "example placeholders present" || bad "example placeholders"

section "Summary"
echo
echo "Passed: $pass  Failed: $fail"
if [[ "$fail" -gt 0 ]]; then
  echo "Smoke test FAILED"
  exit 1
fi
echo "Smoke test OK"
echo
echo "Manual checks in Claude Code (plugin must be installed from this repo or cache):"
echo "  /pr-monitor help"
echo "  /pr-monitor init          # or setup if no config yet"
echo "  /pr-monitor sources"
echo "  /pr-monitor list"
echo "  /pr-checkout help"
echo "  /pr-checkout list"
