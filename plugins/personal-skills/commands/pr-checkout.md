---
name: pr-checkout
description: "Check out a GitHub PR or GitLab MR into a sibling git worktree via git worktree add. Commands: checkout (default), list, remove, help."
argument-hint: "[help|list|remove] [--force] [path:DIR] [remote:NAME] [number|url]"
disable-model-invocation: true
allowed-tools: Read Bash(git *) Bash(gh *) Bash(glab *) Bash(python3 *)
---

# PR Checkout

Check out a GitHub pull request or GitLab merge request into a **sibling git worktree** next to your local clone, using `gh pr checkout` / `glab mr checkout` plus `git worktree add`.

## Naming convention

Run from inside the repository clone. The worktree directory is `{repo_basename}.{number}`:

```
/home/user/git/my-org/my-app       ← cwd
/home/user/git/my-org/my-app.123   ← worktree for MR/PR 123
```

Internal local branches: `pr-{number}` (GitHub) or `mr-{number}` (GitLab).

## Command reference

```
/pr-checkout [verb] [flags] [path:DIR] [remote:NAME] [number|url|target]
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
| `remote:NAME` | checkout, remove | Git remote for repo identity (default: `origin`) |
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
| `/pr-checkout remote:upstream 1092` | Fork clone: PR on upstream remote |
| `/pr-checkout https://github.com/o/r/pull/123` | From GitHub URL |
| `/pr-checkout https://HOST/g/p/-/merge_requests/123` | From GitLab URL |
| `/pr-checkout --force 123` | Remove and recreate existing worktree |

**List / remove**
| Command | Description |
|---------|-------------|
| `/pr-checkout list` | Worktrees for repo in cwd |
| `/pr-checkout list path:~/git/my-org/my-app` | Worktrees for explicit path |
| `/pr-checkout remove 123` | Remove `{repo}.123` worktree |
| `/pr-checkout remove remote:upstream 1092` | Remove using upstream for provider detection |
| `/pr-checkout remove path:~/git/my-org/my-app 123` | Remove from another clone |

After checkout, run the printed `cd` command to enter the worktree.
```

Then **stop**.

## Script discovery

The wrapper delegates to `python3 -m personal_skills.pr_checkout` (stdlib only; no `jq`).

```shell
SCRIPT="$(find ~/.claude/plugins/cache/personal-skills-marketplace/personal-skills \
  -path '*/scripts/pr-checkout/pr_worktree.sh' 2>/dev/null | head -1)"
if [ -z "$SCRIPT" ]; then
  SCRIPT="$HOME/git/personal-skills/plugins/personal-skills/scripts/pr-checkout/pr_worktree.sh"
fi
# Equivalent: python3 -m personal_skills.pr_checkout checkout ...
```

## Parse arguments

From `$ARGUMENTS`, classify tokens:

1. **Verb** — first match among: `help`, `list`, `remove`. If none, verb = checkout.
2. **Flags** — `--force`, `path:DIR` (for list/remove), `remote:NAME` (for checkout/remove; default `origin`).
3. **Checkout target** — remaining token: number or PR/MR URL.
4. **Remove target** — remaining number after `remove`.

## Checkout workflow (default)

1. Require cwd inside a git repository (or URL must match cwd repo remote).
2. Run:
   ```shell
   bash "$SCRIPT" checkout [--force] [--remote NAME] "$TARGET"
   ```
   When `$ARGUMENTS` includes `remote:upstream`, pass `--remote upstream`.
3. Parse JSON from stdout.
4. Print the **`cd_command` field verbatim** in a fenced code block — copy-paste ready:
   ```
   cd /home/user/git/my-org/my-app.123
   ```
5. Also summarize: worktree path, branch, provider, number.
6. **Stop** — do not run other commands unless fetch failed (then show error + fix hint).

On error "worktree already exists", suggest `/pr-checkout --force N` or `/pr-checkout remove N`.

On error `gh pr checkout failed`, suggest checking `git remote -v` and retrying with `remote:upstream` (or the remote that owns the PR), e.g. `/pr-checkout remote:upstream 1092`.

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

1. Parse optional `path:DIR`, optional `remote:NAME` (default `origin`), and required number.
2. Run:
   ```shell
   bash "$SCRIPT" remove [--remote NAME] [--path "$DIR"] [--force] "$NUMBER"
   ```
   When `$ARGUMENTS` includes `remote:upstream`, pass `--remote upstream`.
3. Confirm removal (path removed from `git worktree list`).
4. **Stop**.

## Requirements

- Must run **inside** the target clone for checkout (URL validates against the chosen remote; default `origin`).
- Uses `gh pr checkout` / `glab mr checkout` to fetch PR/MR heads into local `pr-N` / `mr-N` branches, then `git worktree add` for the sibling worktree (does not leave the main clone checked out on the PR/MR branch).
- **Remote selection:** `--remote NAME` / `remote:NAME` (default `origin`). Use `remote:upstream` in fork clones when the PR is filed against the parent repo.
- Refuses to delete unrelated directories at the worktree path (only registered worktrees).
- Requires authenticated `gh` (GitHub) or `glab` (GitLab) for checkout.

## Related

For monitoring open PRs/MRs across many repos, use `/pr-monitor list`.
