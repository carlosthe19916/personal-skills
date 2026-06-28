# personal-skills

A Claude Code plugin with personal skills for everyday development workflows.

## Skills

### npm-vuln-fix

Fixes npm package vulnerabilities (CVEs) by identifying affected packages and applying safe version updates through direct dependency updates or npm overrides.

### pr-monitor

Open PR/MR report across configured GitHub and GitLab repos ([review-rot](https://github.com/conforma/review-rot)-style). Config: `~/.config/personal-skills/pr-monitor/sources.yaml`.

| Command | Description |
|---------|-------------|
| `/pr-monitor list` | Ready-for-review report (daily default) |
| `/pr-monitor all` / `wip` | Include drafts / drafts only |
| `/pr-monitor sources` | List monitored repos (no fetch) |
| `/pr-monitor setup` / `init` | Create or bootstrap config |
| `/pr-monitor org:…` `group:…` `host:…` `repo:…` `author:…` | Narrow scope |
| `/pr-monitor help` | Full cheat sheet |

First run: `/pr-monitor setup` then `/pr-monitor list`. Filters: `org:`, `group:`, `host:`, `repo:`, `author:` — order does not matter.

### pr-checkout

PR/MR into a sibling worktree `{repo}.{number}` via `git worktree add` (run inside the clone).

| Command | Description |
|---------|-------------|
| `/pr-checkout 123` | Create `my-app.123` next to clone |
| `/pr-checkout --force 123` | Recreate existing worktree |
| `/pr-checkout list` | List worktrees (`path:~/git/my-org/my-app` optional) |
| `/pr-checkout remove 123` | Remove worktree + branch |
| `/pr-checkout help` | Cheat sheet |

Prints a copy-paste `cd` path after checkout.

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
   - **Python 3.11+** (for `/pr-monitor` and `/pr-checkout` script helpers)
   - [GitHub CLI](https://cli.github.com/) (`gh auth login`) — for GitHub repos
   - [GitLab CLI](https://gitlab.com/gitlab-org/cli/) (`glab auth login`) — for GitLab repos

   You only need the CLI for providers you configure.

Contributions must pass CI — see the **CI** workflow in the Actions tab (`pytest` under `plugins/personal-skills/`).

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

3. Confirm the installed version in Claude Code's plugin list (should match [`plugin.json`](plugins/personal-skills/.claude-plugin/plugin.json), currently **1.4.0**).

Your user config at `~/.config/personal-skills/pr-monitor/sources.yaml` is **not** overwritten by plugin updates — only the bundled example template in the plugin cache changes.

If commands like `/pr-monitor` or `/pr-checkout` do not appear after updating, restart Claude Code or run `/plugin install` again.

## pr-monitor

**Setup:** `/pr-monitor setup` (interactive) or `/pr-monitor init` then edit `sources.yaml`. Override path with `PR_MONITOR_CONFIG`.

**Auth:** `gh auth login` for GitHub; `glab auth login --hostname HOST` per GitLab instance.

Minimal config (multi-instance GitLab supported):

```yaml
sources:
  github:
    orgs: [{ name: my-github-org }]
    repos: [owner/standalone-repo]
  gitlab:
    instances:
      - host: gitlab.example.com
        groups: [{ name: my-group }]
        repos: [my-group/my-project]
```

Schema and options (`authors`, `bots`, `display.stale_days`, …): [`pr-monitor.sources.example.yaml`](plugins/personal-skills/config/pr-monitor.sources.example.yaml).

## MCP Servers

This plugin includes an [Atlassian MCP](https://mcp.atlassian.com/) server configuration for reading JIRA tickets.

## License

MIT
