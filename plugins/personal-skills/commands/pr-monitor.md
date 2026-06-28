---
name: pr-monitor
description: Monitor open PRs/MRs across GitHub and GitLab. Commands: list (default), sources, setup, init, help.
argument-hint: "[help|list|sources|setup|init] [all|wip] [author:login|org:name|group:name|host:hostname|repo:...]"
disable-model-invocation: true
allowed-tools: Read Edit Write Bash(gh *) Bash(glab *) Bash(jq *) Bash(mkdir *) Bash(cp *) Bash(find *) Bash(test *)
---

# PR Monitor

Monitor open pull requests (GitHub) and merge requests (GitLab) across repositories configured in the user's global config. Supports multiple GitLab instances including self-managed hosts (e.g. `gitlab.cee.redhat.com`).

## Config path

Resolve in this order:

1. `$PR_MONITOR_CONFIG` if set
2. Otherwise `~/.config/personal-skills/pr-monitor/sources.yaml`

## Command reference (UX)

Think in three layers: **verb** → **mode** → **scope filters**. Token order does not matter.

```
/pr-monitor [verb] [mode] [filters...]
```

### Verbs (what to do)

| Verb | Shorthand | Action |
|------|-----------|--------|
| *(none)* | — | Same as `list` — fetch PR/MR report |
| `list` | — | Fetch report from configured sources (recommended; makes intent explicit) |
| `sources` | `repos` | Show which repositories are monitored (resolve config only; **no PR fetch**) |
| `setup` | — | Interactive wizard to create or update config; then **stop** |
| `init` | — | Copy example config (and optionally merge bootstrap tokens); then **stop** |
| `help` | — | Print the cheat sheet below; then **stop** |

If the user types only modifiers (`all`, `author:alice`, `repo:...`) with no verb, treat as **`list`**.

### Modes (what to show) — fetch verbs only

| Mode | Default? | Meaning |
|------|----------|---------|
| *(none)* | **yes** | **Ready** — non-draft, ready-for-review (also honors `filters` in config) |
| `all` | | Include drafts |
| `wip` | | Drafts / WIP only |

Only one mode applies. If both `all` and `wip` appear, **`wip` wins**.

Do **not** require the word `ready` — it is always the default when neither `all` nor `wip` is given.

### Scope filters (narrow which repos)

| Filter | Used with | Meaning |
|--------|-----------|---------|
| `repo:github:owner/name` | `list`, `sources` | Single GitHub repo only (skip config expansion) |
| `repo:owner/name` | `list`, `sources` | Shorthand for GitHub |
| `repo:gitlab:HOST:group/project` | `list`, `sources` | Single GitLab project on a specific instance |
| `repo:gitlab:group/project` | `list`, `sources` | Single GitLab project on gitlab.com |
| `org:NAME` | `list`, `sources` | GitHub org only (repos from that org + explicit repos under it in config) |
| `group:NAME` | `list`, `sources` | GitLab group only; use with `host:` when multiple instances |
| `host:HOSTNAME` | `list`, `sources` | GitLab instance only (all groups/repos on that host from config) |
| `author:LOGIN` | `list` | Filter report to one author (fetch flag `--author`) |

**Init-only bootstrap tokens** (only when `init` is present — merge into config, do not fetch):

| Token | Writes to |
|-------|-----------|
| `org:NAME` | `sources.github.orgs` |
| `host:HOSTNAME` | `sources.gitlab.instances[]` (normalize URL → hostname) |
| `group:NAME` | groups on the **last** GitLab instance (use `host:` first to target the right one) |
| `repo:...` | `sources.github.repos` or matching GitLab instance `repos` |
| `author:LOGIN` | `authors` |

### Precedence rules

1. **`help`**, **`setup`**, **`init`** → run that verb only; ignore modes (except `init` bootstrap tokens).
2. **`sources`** / **`repos`** → resolve and display repo inventory; ignore modes and `author:`.
3. **`list`** / default → preflight → resolve repos → fetch → filter → report.
4. **`repo:...`** → single-repo scope; ignore config expansion (still run preflight for that provider).
5. **`org:`**, **`group:`**, **`host:`** → narrow config expansion (combinable; intersect when multiple are set).
6. Unknown tokens → print **`help`** excerpt and ask the user to retry.

### Cheat sheet (`help` output)

When `$ARGUMENTS` contains `help`, print this (adapt examples to the user's config if known):

```markdown
# PR Monitor — commands

**Report (default)** — open PRs/MRs needing review
| Command | Description |
|---------|-------------|
| `/pr-monitor` | All configured repos, ready for review |
| `/pr-monitor list` | Same (explicit) |
| `/pr-monitor all` | Include drafts |
| `/pr-monitor wip` | Drafts only |
| `/pr-monitor author:alice` | Filter by author |
| `/pr-monitor org:my-org` | One GitHub org |
| `/pr-monitor host:gitlab.cee.redhat.com` | One GitLab instance |
| `/pr-monitor group:trustification host:gitlab.cee.redhat.com` | One GitLab group |
| `/pr-monitor repo:github:owner/name` | One GitHub repo (ad-hoc) |
| `/pr-monitor repo:gitlab:HOST:group/project` | One GitLab project (ad-hoc) |

**Inspect** — no API fetch for PRs
| Command | Description |
|---------|-------------|
| `/pr-monitor sources` | List all repositories resolved from config |
| `/pr-monitor sources org:my-org` | Repos that would be scanned for one org |

**Configure**
| Command | Description |
|---------|-------------|
| `/pr-monitor setup` | Interactive wizard (recommended first run) |
| `/pr-monitor init` | Copy example template to edit manually |
| `/pr-monitor init org:foo host:gitlab.com group:bar` | Bootstrap config in one step |

**Local checkout:** `/pr-checkout 123` creates `my-app.123` next to your clone — see `/pr-checkout help`.

Config: `~/.config/personal-skills/pr-monitor/sources.yaml` (or `$PR_MONITOR_CONFIG`)
```

Then **stop** — do not fetch.

## Parse arguments

From `$ARGUMENTS`, classify each whitespace-separated token:

1. **Verb** — first match among: `help`, `setup`, `init`, `sources`, `repos`, `list`. Map `repos` → `sources`. If none, verb = `list`.
2. **Mode** — if verb is `list` (or default): `all`, `wip` (ignore `ready`; it is the default).
3. **Filters** — all `key:value` tokens (see scope filters table). For `init`, bootstrap tokens merge into config.
4. Strip consumed tokens; anything unrecognized triggers the help excerpt.

### Examples

| Invocation | Verb | Mode | Scope |
|------------|------|------|-------|
| `/pr-monitor` | list | ready | all configured repos |
| `/pr-monitor list` | list | ready | all configured repos |
| `/pr-monitor all` | list | all | all configured repos |
| `/pr-monitor list wip org:conforma` | list | wip | GitHub org `conforma` only |
| `/pr-monitor sources` | sources | — | show resolved repo list |
| `/pr-monitor sources host:gitlab.cee.redhat.com` | sources | — | one GitLab instance |
| `/pr-monitor repo:github:foo/bar wip` | list | wip | single repo |
| `/pr-monitor setup` | setup | — | — |
| `/pr-monitor init org:acme host:gitlab.com group:platform` | init | — | bootstrap config |
| `/pr-monitor help` | help | — | — |

## Interactive setup (`setup`)

When `$ARGUMENTS` contains `setup`, run this wizard **in the chat** and **do not fetch PRs**. Goal: produce a complete, placeholder-free [`sources.yaml`](~/.config/personal-skills/pr-monitor/sources.yaml).

### Step 0 — Prepare

1. Resolve config path (`$PR_MONITOR_CONFIG` or `~/.config/personal-skills/pr-monitor/sources.yaml`).
2. `mkdir -p ~/.config/personal-skills/pr-monitor`
3. `Read` existing config if present.
4. Check CLI auth and tell the user upfront if login is needed:
   - `gh auth status` → else instruct `gh auth login`
   - For GitLab: `glab auth status --all` (or note they will need `glab auth login --hostname HOST` per instance)

### Step 1 — Existing config

If config already exists with real (non-placeholder) values, show a short summary (GitHub orgs/repos, GitLab instances/groups/repos, authors) and ask:

> **A)** Start fresh (replace config)  
> **B)** Add to existing config  
> **C)** Edit specific sections only  

Wait for the user's answer before continuing.

If no config exists, treat as **start fresh**.

### Step 2 — GitHub sources (optional)

Ask: *"Do you want to monitor GitHub repositories? (yes/no)"*

If **yes**, collect (one message or several — user can paste lists):

- **GitHub orgs** — all repos in each org are monitored (e.g. `conforma`, `my-org`). Comma-separated or one per line.
- **Explicit GitHub repos** — outside those orgs (e.g. `owner/repo`). Comma-separated or one per line.

For each org, optionally verify access:

```shell
gh api orgs/ORG --jq .login 2>/dev/null || echo "cannot access ORG"
```

For each explicit repo:

```shell
gh repo view owner/repo --json nameWithOwner -q .nameWithOwner 2>/dev/null
```

Report any failures; ask whether to skip or fix them.

If **no** GitHub sources, leave `sources.github` empty or omit orgs/repos lists.

### Step 3 — GitLab sources (repeat per instance)

Ask: *"Do you want to monitor GitLab merge requests? (yes/no)"*

If **yes**, for **each GitLab instance** ask:

1. **Host** — e.g. `gitlab.cee.redhat.com`, `gitlab.com`, or full URL (normalize to hostname only).
2. **Groups** — all projects in group + subgroups (e.g. `trustification`). Comma-separated.
3. **Explicit projects** — `group/project` or `group/subgroup/project`. Comma-separated.

Verify auth before probing repos:

```shell
glab auth status --hostname HOST
```

Verify group/project access when possible:

```shell
GITLAB_HOST=HOST glab repo view group/project 2>/dev/null
GITLAB_HOST=HOST glab repo list -g GROUP -G --per-page 5 --output json --jq '.[].path_with_namespace' 2>/dev/null | head -5
```

After each instance, ask: *"Add another GitLab instance? (yes/no)"*

If **no** GitLab sources, leave `sources.gitlab.instances` empty or omit.

### Step 4 — Optional filters

Ask only if the user wants to customize (defaults are fine for most users):

- **Authors allowlist** — usernames whose MRs/PRs are always shown even outside configured orgs/groups (comma-separated, or skip)
- **Bot accounts** — flagged as automated (e.g. `dependabot[bot]`, `renovate-bot`, or skip)
- **Dashboard title** — default `"My PR Monitor"`

### Step 5 — Write config

Build YAML in the **multi-instance format** (no placeholder values):

```yaml
sources:
  github:
    orgs:
      - name: ORG
    repos:
      - owner/repo
  gitlab:
    instances:
      - host: gitlab.cee.redhat.com
        groups:
          - name: GROUP
        repos:
          - group/project
authors: []
bots:
  - dependabot[bot]
filters:
  exclude_drafts: true
  ready_for_review_only: true
display:
  title: "My PR Monitor"
  sort_by: updated_at
  sort_dir: desc
  stale_days: 3
```

- **Start fresh** → `Write` the full file.
- **Add to existing** → `Read` + `Edit` to merge new orgs/repos/instances without duplicating entries.
- **Edit sections** → change only what the user requested.

Omit empty lists (`orgs: []`) — use empty arrays only when the section exists but has no entries yet.

### Step 6 — Confirm

1. Print the final config path and a human-readable summary table:

| Provider | Scope | Value |
|----------|-------|-------|
| GitHub | org | conforma |
| GitHub | repo | owner/extra |
| GitLab | gitlab.cee.redhat.com / group | trustification |
| GitLab | gitlab.cee.redhat.com / repo | trustification/trustify |

2. Remind about GitLab auth if any instance was added:
   ```shell
   glab auth login --hostname gitlab.cee.redhat.com
   ```

3. Tell the user to run `/pr-monitor list` to test, or `/pr-monitor setup` again to add more repos.

**Stop** after setup — do not run fetch unless the user explicitly asks in the same turn.

### Setup vs init vs list

| Command | Use when |
|---------|----------|
| `/pr-monitor help` | You forget syntax or want the cheat sheet |
| `/pr-monitor list` | Daily use — full ready-for-review report |
| `/pr-monitor sources` | Verify which repos are configured before a slow fetch |
| `/pr-monitor setup` | First time or guided add/change of sources |
| `/pr-monitor init` | Quick template copy or one-line bootstrap |
| `/pr-monitor init org:foo host:gitlab.com group:bar` | Non-interactive bootstrap |

## Init / bootstrap (non-interactive)

If `$ARGUMENTS` contains `init`, or config file is missing when a fetch is requested (and `setup` was **not** requested):

1. If live config already exists and args contain only `init` with tokens, merge those into the existing file and stop.
2. Otherwise create config directory:
   ```shell
   mkdir -p ~/.config/personal-skills/pr-monitor
   ```
3. If live config does not exist, copy the bundled example:
   ```shell
   EXAMPLE="$(find ~/.claude/plugins/cache/personal-skills-marketplace/personal-skills \
     -name 'pr-monitor.sources.example.yaml' 2>/dev/null | head -1)"
   if [ -z "$EXAMPLE" ]; then
     EXAMPLE="$(find "$HOME/git/personal-skills/plugins/personal-skills/config" \
       -name 'pr-monitor.sources.example.yaml' 2>/dev/null | head -1)"
   fi
   cp "$EXAMPLE" ~/.config/personal-skills/pr-monitor/sources.yaml
   ```
4. If `init` had tokens, merge into config:
   - `org:NAME` → `sources.github.orgs`
   - `host:HOSTNAME` → add or update entry in `sources.gitlab.instances[]` (strip `https://` and trailing `/`)
   - `group:NAME` → add to the **last** instance in `sources.gitlab.instances[]` (use `host:` first to target the right instance)
   - `repo:github:owner/name` or `repo:owner/name` → `sources.github.repos`
   - `repo:gitlab:HOST:group/project` → repos under matching instance host
   - `repo:gitlab:group/project` → repos under gitlab.com instance
   - `author:LOGIN` → `authors`
5. Tell the user to edit sources, then re-run `/pr-monitor list`.
6. **Stop** — do not fetch until config has real (non-placeholder) sources.

Placeholder values to reject on fetch: `my-org`, `my-github-org`, `my-public-group`, `trustification/trustify`, `owner/standalone-repo`, `teammate-a`.

## Show sources (`sources` / `repos`)

When verb is `sources` or `repos`:

1. Run preflight (auth + config validation) — same as fetch.
2. Resolve repositories (below), applying `org:`, `group:`, `host:`, or `repo:` scope filters.
3. Render an inventory table — **do not** run `fetch_prs.sh`:

```markdown
# PR Monitor — monitored repositories ({count})

| Provider | Instance | Repository |
|----------|----------|------------|
| GitHub | — | owner/repo |
| GitLab | gitlab.cee.redhat.com | group/project |
```

4. End with: *Run `/pr-monitor list` to fetch open PRs/MRs from these repos.*

**Stop** after sources — do not fetch PRs unless the user asks in the same turn.

## Preflight (before fetch or sources)

1. Read the live config and determine which providers are configured
2. If GitHub sources present: `gh auth status` — if it fails, instruct `gh auth login` (`repo` scope for private repos)
3. If GitLab sources present: for **each unique** `host` in `sources.gitlab.instances[]` (or legacy `sources.gitlab.host`):
   ```shell
   glab auth status --hostname HOST
   ```
   If it fails, instruct:
   ```shell
   glab auth login --hostname HOST
   ```
   User can verify all instances with `glab auth status --all`.
4. Validate at least one real source exists
5. Reject if only placeholders remain

## Config format

### Preferred (multi-instance GitLab)

```yaml
sources:
  github:
    orgs: [{ name: my-org }]
    repos: [owner/repo]
  gitlab:
    instances:
      - host: gitlab.cee.redhat.com
        groups: [{ name: trustification }]
        repos: [trustification/trustify]
      - host: gitlab.com
        groups: [{ name: my-public-group }]
        repos: []
```

### Legacy single-instance GitLab shorthand

```yaml
sources:
  gitlab:
    host: gitlab.cee.redhat.com   # optional; default gitlab.com
    groups: [{ name: my-group }]
    repos: [group/project]
```

Treat as one entry in `instances[]` with that host.

### Legacy GitHub-only format

```yaml
sources:
  orgs: [{ name: my-org }]
  repos: [owner/repo]
```

**Host normalization:** accept `https://gitlab.cee.redhat.com/` or `gitlab.cee.redhat.com`; use hostname only in fetch args.

## Resolve repositories

Unless `repo:...` was passed in arguments:

Apply scope filters when present (intersect when multiple):

- **`org:NAME`** — only expand that GitHub org; include explicit `sources.github.repos` only if they belong to that org (`owner` matches org name or repo is listed under that org in config). Skip GitLab entirely.
- **`host:HOSTNAME`** — only GitLab instances whose normalized host matches; skip GitHub unless no host filter was meant for mixed configs (when `host:` is set, GitHub is skipped).
- **`group:NAME`** — only that group within the selected instance(s). If `host:` is also set, restrict to that instance; if only one instance exists in config, use it; if multiple and no `host:`, expand the group on **every** instance that has a matching group name in config.
- No scope filters — expand everything (default for `list` and `sources`).

### GitHub

1. Collect org names from `sources.github.orgs[].name` (or legacy `sources.orgs`) — if `org:NAME` filter set, use only that org
2. For each org:
   ```shell
   gh repo list ORG --limit 1000 --json nameWithOwner -q '.[].nameWithOwner'
   ```
3. Append explicit repos from `sources.github.repos` (or legacy `sources.repos`) — when `org:` filter is active, keep only repos whose owner equals the org

### GitLab

For each entry in `sources.gitlab.instances[]` (or legacy single block with optional `host`):

1. Normalize `host` (default `gitlab.com` if omitted) — skip instance if `host:FILTER` was passed and does not match
2. For each group in that instance — if `group:FILTER` was passed, only expand matching group names
   ```shell
   GITLAB_HOST=HOST glab repo list -g GROUP -G --per-page 100 --output json \
     --jq '.[].path_with_namespace'
   ```
3. Append explicit repos from that instance's `repos` list — when `group:` filter is active, keep only repos whose path starts with `GROUP/`

If scope filters yield **zero** repos, say so clearly and suggest `/pr-monitor sources` (no filters) or `/pr-monitor setup`.

### Prefix for fetch script

- GitHub → `github:owner/repo`
- GitLab → `gitlab:HOST:group/project` (always include host)

Deduplicate the combined list.

If `repo:...` was passed:
- `repo:gitlab:HOST:group/project` → `gitlab:HOST:group/project`
- `repo:gitlab:group/project` → `gitlab:gitlab.com:group/project`

## Fetch PRs/MRs

Locate the fetch script:

```shell
SCRIPT="$(find ~/.claude/plugins/cache/personal-skills-marketplace/personal-skills \
  -path '*/scripts/pr-monitor/fetch_prs.sh' 2>/dev/null | head -1)"
if [ -z "$SCRIPT" ]; then
  SCRIPT="$HOME/git/personal-skills/plugins/personal-skills/scripts/pr-monitor/fetch_prs.sh"
fi
```

Build fetch flags from mode and author:

| Mode | Script flags |
|------|--------------|
| `ready` | `--ready` |
| `all` | `--include-drafts` |
| `wip` | `--wip` |
| `author:LOGIN` | add `--author LOGIN` |

Run:

```shell
bash "$SCRIPT" [flags] github:owner/repo gitlab:gitlab.cee.redhat.com:group/project ...
```

Parse the JSON array output. GitLab items include `provider`, `instance` (hostname), and `repo`.

## Apply config-level filters

After fetch, apply rules from config:

1. **Author allowlist** (`authors` list): if non-empty, keep items where:
   - repo belongs to a configured org/group (same instance for GitLab), **or**
   - author is in `authors`
2. **Bots** (`bots` list): set `is_automated: true` on matching authors
3. **Config filters**: respect `filters.exclude_drafts` and `filters.ready_for_review_only` when mode is default `ready`

Track org/group/instance membership for filter step.

## Sort

Use `display.sort_by` and `display.sort_dir` from config (default: `updated_at` desc).

## Render report

Use `display.title` from config (default: "PR Monitor").

When multiple GitLab instances are configured, show **Instance** column. Otherwise omit it for GitHub-only or single-instance GitLab.

Format:

```markdown
# {title} — {count} open PRs/MRs (generated {UTC timestamp})

| PR/MR | Repo | Instance | Author | CI | Updated | Age | Reviews | Notes |
|-------|------|----------|--------|----|---------|-----|---------|-------|
| [#{n} {title}]({url}) | {repo} | {instance or —} | {author} | {ci} | {relative} | {age} | {review_count} | {notes} |
```

For GitLab rows with instance set, repo column can show `{instance}/{repo}` when helpful.

Column rules:

- **Instance**: GitLab hostname (e.g. `gitlab.cee.redhat.com`); `—` for GitHub
- **CI**: `SUCCESS` → ✓, `FAILURE` → ✗, `PENDING` → …, null → —
- **Notes**: `draft`, `automated`, `ready`; prefix `**stale**` if age > `display.stale_days` (default 3)

End with summary:

```markdown
## Summary
- Ready: {n}
- Drafts: {n}
- Failing CI: {n}
- Automated: {n}
- Stale (>{stale_days}d): {n}
- GitHub: {n} | GitLab: {n}
```

Per-instance GitLab counts when multiple instances configured.

If no PRs match, say so and suggest `/pr-monitor all`, `/pr-monitor sources`, or `/pr-monitor help`.
