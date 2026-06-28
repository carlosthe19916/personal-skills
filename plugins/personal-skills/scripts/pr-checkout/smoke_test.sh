#!/usr/bin/env bash
# Smoke tests for pr-checkout — run before publishing.
# Usage: bash plugins/personal-skills/scripts/pr-checkout/smoke_test.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SCRIPT="$ROOT/scripts/pr-checkout/pr_worktree.sh"
CMD_DOC="$ROOT/commands/pr-checkout.md"

pass=0
fail=0

ok() { echo "  ✓ $*"; pass=$((pass + 1)); }
bad() { echo "  ✗ $*"; fail=$((fail + 1)); }

section() { echo; echo "== $* =="; }

section "Static checks"
bash -n "$SCRIPT" && ok "pr_worktree.sh syntax" || bad "pr_worktree.sh syntax"
command -v jq >/dev/null 2>&1 && ok "jq installed" || bad "jq installed"
[[ -f "$CMD_DOC" ]] && ok "pr-checkout command doc exists" || bad "pr-checkout command doc exists"
[[ -x "$SCRIPT" ]] && ok "pr_worktree.sh executable" || bad "pr_worktree.sh executable"

section "CLI help"
if (bash "$SCRIPT" --help 2>&1 || true) | grep -q "my-app.123"; then
  ok "--help mentions naming example"
else
  bad "--help mentions naming example"
fi

if (bash "$SCRIPT" checkout 2>&1 || true) | grep -q "checkout requires"; then
  ok "checkout requires argument"
else
  bad "checkout requires argument"
fi

if (bash "$SCRIPT" remove 2>&1 || true) | grep -q "remove requires"; then
  ok "remove requires argument"
else
  bad "remove requires argument"
fi

section "Path computation (unit)"
source_smoke() {
  REPO_ROOT="/home/user/git/my-org/my-app"
  REPO_NAME="$(basename "$REPO_ROOT")"
  NUMBER="123"
  WORKTREE_PATH="$(dirname "$REPO_ROOT")/${REPO_NAME}.${NUMBER}"
  [[ "$WORKTREE_PATH" == "/home/user/git/my-org/my-app.123" ]]
}
source_smoke && ok "worktree path my-app.123" || bad "worktree path my-app.123"

section "Provider detection (unit)"
# shellcheck source=pr_worktree.sh
source "$SCRIPT"

if [[ "$(detect_provider_from_origin 'git@gitlab.example.com:group/project.git')" == "gitlab" ]]; then
  ok "gitlab SSH host"
else
  bad "gitlab SSH host"
fi

if [[ "$(detect_provider_from_origin 'git@github.mycompany.com:org/repo.git')" == "github" ]]; then
  ok "GitHub Enterprise SSH host"
else
  bad "GitHub Enterprise SSH host"
fi

if [[ "$(detect_provider_from_origin 'git@code.example.com:org/repo.git')" == "unknown" ]]; then
  ok "unknown host not classified as gitlab"
else
  bad "unknown host not classified as gitlab"
fi

section "URL parsing (unit, no network)"
parse_github() {
  local arg="https://github.com/owner/repo/pull/42"
  [[ "$arg" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]
  [[ "${BASH_REMATCH[1]}" == "owner/repo" && "${BASH_REMATCH[2]}" == "42" ]]
}
parse_github && ok "GitHub URL regex" || bad "GitHub URL regex"

parse_gitlab() {
  local arg="https://gitlab.example.com/group/project/-/merge_requests/17"
  [[ "$arg" =~ ^https?://([^/]+)/(.+)/-/merge_requests/([0-9]+) ]]
  [[ "${BASH_REMATCH[1]}" == "gitlab.example.com" ]]
  [[ "${BASH_REMATCH[2]}" == "group/project" ]]
  [[ "${BASH_REMATCH[3]}" == "17" ]]
}
parse_gitlab && ok "GitLab URL regex" || bad "GitLab URL regex"

section "Integration (temp repo)"
TMP="$ROOT/.smoke-worktree-test-$$"
rm -rf "$TMP"
mkdir -p "$TMP"
trap 'rm -rf "$TMP"' EXIT

git init --bare "$TMP/remote.git" >/dev/null 2>&1
git clone "$TMP/remote.git" "$TMP/my-app" >/dev/null 2>&1
git -C "$TMP/my-app" config user.email "test@example.com"
git -C "$TMP/my-app" config user.name "Test"
git -C "$TMP/my-app" -c commit.gpgsign=false commit --allow-empty -m "init" >/dev/null 2>&1
git -C "$TMP/my-app" remote set-url origin "https://github.com/example/my-app.git"
git -C "$TMP/my-app" branch pr-7 >/dev/null 2>&1
git -C "$TMP/my-app" worktree add "$TMP/my-app.7" pr-7 >/dev/null 2>&1

list_count="$(bash "$SCRIPT" list --path "$TMP/my-app" | jq '.worktrees | length')"
if [[ "$list_count" == "1" ]]; then
  ok "list finds sibling worktree"
else
  bad "list finds sibling worktree (got ${list_count})"
fi

list_number="$(bash "$SCRIPT" list --path "$TMP/my-app" | jq -r '.worktrees[0].number')"
if [[ "$list_number" == "7" ]]; then
  ok "list number from branch pr-7"
else
  bad "list number from branch pr-7 (got ${list_number})"
fi

bash "$SCRIPT" remove --path "$TMP/my-app" 7 >/dev/null
if [[ ! -d "$TMP/my-app.7" ]]; then
  ok "remove deletes worktree directory"
else
  bad "remove deletes worktree directory"
fi

section "Summary"
echo
echo "Passed: $pass  Failed: $fail"
if [[ "$fail" -gt 0 ]]; then
  echo "Smoke test FAILED"
  exit 1
fi
echo "Smoke test OK"
