# personal-skills

A Claude Code plugin with personal skills for everyday development workflows.

## Skills

### npm-vuln-fix

Fixes npm package vulnerabilities (CVEs) by identifying affected packages and applying safe version updates through direct dependency updates or npm overrides.

### pr-monitor

Monitors open pull requests (GitHub) and merge requests (GitLab) across multiple repositories and shows a sorted report of what needs review — inspired by [review-rot](https://github.com/conforma/review-rot), delivered as a chat/terminal report.

Supports **multiple GitLab instances**, including self-managed hosts like `gitlab.cee.redhat.com`.

## Installation

1. Add the marketplace:
   ```
   /plugin marketplace add carlosthe19916/personal-skills
   ```

2. Install the plugin:
   ```
   /plugin install personal-skills@personal-skills-marketplace
   ```

3. Prerequisites:
   - [GitHub CLI](https://cli.github.com/) (`gh auth login`) — for GitHub repos
   - [GitLab CLI](https://gitlab.com/gitlab-org/cli/) (`glab auth login`) — for GitLab repos
   - `jq` (usually preinstalled on Linux; `dnf install jq` on Fedora)

   You only need the CLI for providers you configure.

## Updating the plugin

After new releases are pushed to GitHub, refresh your local install:

1. Update the marketplace catalog (pulls latest plugin metadata from the repo):
   ```
   /plugin marketplace update carlosthe19916/personal-skills
   ```

2. Reinstall or upgrade the plugin:
   ```
   /plugin install personal-skills@personal-skills-marketplace
   ```

3. Confirm the installed version in Claude Code's plugin list (should match [`plugin.json`](plugins/personal-skills/.claude-plugin/plugin.json), currently **1.3.0**).

Your user config at `~/.config/personal-skills/pr-monitor/sources.yaml` is **not** overwritten by plugin updates — only the bundled example template in the plugin cache changes.

If commands like `/pr-monitor` do not appear after updating, restart Claude Code or run `/plugin install` again.

## pr-monitor setup

Config is stored per-user (survives plugin upgrades):

```
~/.config/personal-skills/pr-monitor/sources.yaml
```

Override with `PR_MONITOR_CONFIG=/path/to/sources.yaml`.

### First run (interactive)

Recommended — guided setup in chat:

```
/pr-monitor setup
```

The agent will ask which GitHub orgs/repos and GitLab instances/groups/projects to monitor, verify access with `gh`/`glab` where possible, and write `~/.config/personal-skills/pr-monitor/sources.yaml` for you.

You can run `/pr-monitor setup` again anytime to add more sources (choose "add to existing" when prompted).

### First run (manual)

Quick template copy if you prefer editing the file yourself:

```
/pr-monitor init
```

Edit `sources.github` and/or `sources.gitlab.instances` with your orgs, groups, and repositories, then run:

```
/pr-monitor list
```

Or bootstrap with values in one step:

```
/pr-monitor init host:gitlab.cee.redhat.com group:trustification org:my-github-org author:teammate
```

### GitLab self-managed authentication

Authenticate **each** GitLab instance you configure:

```bash
glab auth login --hostname gitlab.cee.redhat.com
glab auth login --hostname gitlab.com
glab auth status --all
```

When `/pr-monitor` or `/pr-monitor list` runs outside a git repository, `glab` defaults to gitlab.com unless the config host is passed via `GITLAB_HOST` — the fetch script handles this automatically.

### Config example (multi-instance)

```yaml
sources:
  github:
    orgs:
      - name: my-github-org
    repos:
      - owner/standalone-repo

  gitlab:
    instances:
      - host: gitlab.cee.redhat.com
        groups:
          - name: trustification
        repos:
          - trustification/trustify

      - host: gitlab.com
        groups:
          - name: my-public-group
        repos: []

authors:
  - teammate-a

display:
  title: "My PR Monitor"
  stale_days: 3
```

Legacy formats still supported:
- Single-instance GitLab: `sources.gitlab.host` + `groups` / `repos`
- GitHub-only: top-level `sources.orgs` / `sources.repos`

See [`plugins/personal-skills/config/pr-monitor.sources.example.yaml`](plugins/personal-skills/config/pr-monitor.sources.example.yaml) for the full schema.

### Usage

Commands use **verb → mode → filters**. Order does not matter. Run `/pr-monitor help` anytime for the full cheat sheet.

#### Report (default)

Open PRs/MRs from your configured sources. Default mode is **ready** (non-draft, ready for review).

| Command | Description |
|---------|-------------|
| `/pr-monitor list` | All configured repos — **recommended daily command** |
| `/pr-monitor` | Same as `list` |
| `/pr-monitor all` | Include drafts |
| `/pr-monitor wip` | Drafts / WIP only |
| `/pr-monitor author:alice` | Filter by author |
| `/pr-monitor org:my-org` | One GitHub org only |
| `/pr-monitor host:gitlab.cee.redhat.com` | One GitLab instance only |
| `/pr-monitor group:trustification host:gitlab.cee.redhat.com` | One GitLab group |
| `/pr-monitor repo:github:owner/name` | Single GitHub repo (ad-hoc) |
| `/pr-monitor repo:gitlab:HOST:group/project` | Single GitLab project (ad-hoc) |

#### Inspect (no PR fetch)

| Command | Description |
|---------|-------------|
| `/pr-monitor sources` | List repositories resolved from config |
| `/pr-monitor repos` | Alias for `sources` |
| `/pr-monitor sources org:my-org` | Preview repos for one org |

#### Configure

| Command | Description |
|---------|-------------|
| `/pr-monitor setup` | Interactive wizard (recommended first run) |
| `/pr-monitor init` | Copy example config template |
| `/pr-monitor init org:foo host:gitlab.com group:bar` | Bootstrap config in one step |

#### Help

| Command | Description |
|---------|-------------|
| `/pr-monitor help` | Print command cheat sheet |

## MCP Servers

This plugin includes an [Atlassian MCP](https://mcp.atlassian.com/) server configuration for reading JIRA tickets.

## License

MIT
