# personal-skills

A Claude Code plugin with personal skills for everyday development workflows.

## Skills

### npm-vuln-fix

Fixes npm package vulnerabilities (CVEs) by identifying affected packages and applying safe version updates through direct dependency updates or npm overrides.

**Usage:**

```
/personal-skills:npm-vuln-fix PROJ-1234
```

The skill will:

1. Read the JIRA ticket to extract the CVE, affected package, and safe version
2. Diagnose whether it's a direct or transitive dependency
3. Apply the appropriate fix (version bump or npm override)
4. Verify the CVE is resolved

## Installation

```
/install-plugin https://github.com/carlosthe19916/personal-skills
```

## MCP Servers

This plugin includes an [Atlassian MCP](https://mcp.atlassian.com/) server configuration for reading JIRA tickets.

## License

MIT
