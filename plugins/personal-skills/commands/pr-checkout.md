---
name: pr-checkout
description: Check out a GitHub PR or GitLab MR into a sibling git worktree via git worktree add. Commands: checkout (default), list, remove, help.
argument-hint: "[help|list|remove] [--force] [path:DIR] [number|url]"
disable-model-invocation: true
allowed-tools: Read Bash(git *) Bash(gh *) Bash(glab *) Bash(jq *)
---

# PR Checkout

Check out a GitHub pull request or GitLab merge request into a **sibling git worktree** next to your local clone, using native `git fetch` + `git worktree add`.

## Naming convention

Run from inside the repository clone. The worktree directory is `{repo_basename}.{number}`:

```
/home/user/git/my-org/my-app       ← cwd
/home/user/git/my-org/my-app.123   ← worktree for MR/PR 123
```

Internal local branches: `pr-{number}` (GitHub) or `mr-{number}` (GitLab).

## Command reference

```
/pr-checkout [verb] [flags] [path:DIR] [number|url|target]
```

### Verbs

| Verb | Default? | Action |
|------|----------|--------|
| *(none)* / number / URL | **yes** | Checkout PR/MR into sibling worktree |
| `list` | | List PR/MR worktrees for this repo |
| `remove` | | Remove worktree + local branch |
| `help` | | Print cheat sheet; **stop** |

### Flags

| Flag | Applies to | Meaning |
|------|------------|---------|
| `--force` | checkout | Replace existing worktree or local `pr-N` / `mr-N` branch |
| `path:DIR` | list, remove | Target a local clone without cd'ing into it (supports `~`) |

### Precedence

1. **`help`** → print cheat sheet; **stop**
2. **`list`** → list worktrees; **stop**
3. **`remove`** → remove by number; **stop**
4. Otherwise → **checkout** (first non-flag token is number or URL)

### Cheat sheet (`help` output)

When `$ARGUMENTS` contains `help`, print:

```markdown
# PR Checkout — commands

**Checkout (default)** — sibling git worktree via `git worktree add`
| Command | Description |
|---------|-------------|
| `/pr-checkout 123` | PR/MR number in current repo → creates `{repo}.123` |
| `/pr-checkout https://github.com/o/r/pull/123` | From GitHub URL |
| `/pr-checkout https://HOST/g/p/-/merge_requests/123` | From GitLab URL |
| `/pr-checkout --force 123` | Remove and recreate existing worktree |

**List / remove**
| Command | Description |
|---------|-------------|
| `/pr-checkout list` | Worktrees for repo in cwd |
| `/pr-checkout list path:~/git/my-org/my-app` | Worktrees for explicit path |
| `/pr-checkout remove 123` | Remove `{repo}.123` worktree |
| `/pr-checkout remove path:~/git/my-org/my-app 123` | Remove from another clone |

After checkout, run the printed `cd` command to enter the worktree.
```

Then **stop**.

## Script discovery

```shell
SCRIPT="$(find ~/.claude/plugins/cache/personal-skills-marketplace/personal-skills \
  -path '*/scripts/pr-checkout/pr_worktree.sh' 2>/dev/null | head -1)"
if [ -z "$SCRIPT" ]; then
  SCRIPT="$HOME/git/personal-skills/plugins/personal-skills/scripts/pr-checkout/pr_worktree.sh"
fi
```

## Parse arguments

From `$ARGUMENTS`, classify tokens:

1. **Verb** — first match among: `help`, `list`, `remove`. If none, verb = checkout.
2. **Flags** — ` --force`, `path:DIR` (for list/remove).
3. **Checkout target** — remaining token: number or PR/MR URL.
4. **Remove target** — remaining number after `remove`.

## Checkout workflow (default)

1. Require cwd inside a git repository (or URL must match cwd repo remote).
2. Run:
   ```shell
   bash "$SCRIPT" checkout [--force] "$TARGET"
   ```
3. Parse JSON from stdout.
4. Print the **`cd_command` field verbatim** in a fenced code block — copy-paste ready:
   ```
   cd /home/user/git/my-org/my-app.123
   ```
5. Also summarize: worktree path, branch, provider, number.
6. **Stop** — do not run other commands unless fetch failed (then show error + fix hint).

On error "worktree already exists", suggest `/pr-checkout --force N` or `/pr-checkout remove N`.

## List workflow

1. Parse optional `path:DIR`.
2. Run:
   ```shell
   bash "$SCRIPT" list [--path "$DIR"]
   ```
3. Render markdown table from JSON:

```markdown
# PR Checkout — worktrees ({count})
Repo: `{repo_root}`

| Directory | Branch | PR/MR | Head | Enter |
|-----------|--------|-------|------|-------|
| my-app.123 | mr-123 | MR !123 | abc1234 | `cd /full/path/my-app.123` |
```

4. If empty: *No PR/MR worktrees found. Use `/pr-checkout 123` to create one.*
5. Footer: *Remove: `/pr-checkout remove 123`*
6. **Stop**.

## Remove workflow

1. Parse optional `path:DIR` and required number.
2. Run:
   ```shell
   bash "$SCRIPT" remove [--path "$DIR"] [--force] "$NUMBER"
   ```
3. Confirm removal (path removed from `git worktree list`).
4. **Stop**.

## Requirements

- Must run **inside** the target clone for checkout (URL validates against `origin`).
- Uses native git only for worktree lifecycle — not `gh pr checkout` / `glab mr checkout`.
- Fetch remote: `origin` if present, otherwise the first configured remote.
- Refuses to delete unrelated directories at the worktree path (only registered worktrees).
- `gh` / `glab` auth checked when provider is detected (optional if fetch works without them).

## Related

For monitoring open PRs/MRs across many repos, use `/pr-monitor list`.
