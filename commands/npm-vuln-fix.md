---
name: npm-vuln-fix
description: Fixes Vulnerability CVE in the npm package dependencies.
argument-hint: "[JIRA]"
disable-model-invocation: true
allowed-tools: Read Edit Grep Bash(npm list *) Bash(npm explain *) Bash(npm audit *) Bash(npm install *) Bash(npm ci) Bash(grep *) mcp__atlassian__*
---

# NPM Vulnerability Fix Assistant

## Identify CVE and Package

$ARGUMENTS read the JIRA ticket and extract:

- **CVE**: Pattern `CVE-year-number` (e.g. `CVE-2026-4800`)
- **Package**: The npm package affected
- **Safe version**: The minimum version that fixes the CVE

## Diagnose

```shell
npm ci
npm audit --json
```

- Use `npm list '<package>'` to confirm the package exists in our dependencies
- Use `npm explain '<package>'` to understand the dependency tree
- Determine if it is a **direct** dependency (in a workspace `package.json`) or **transitive**

## Fix

- **Direct dependency**: Update the version in the workspace `package.json` and run `npm install`
- **Transitive dependency**: Add an `overrides` entry in the root `package.json` to force the safe version:
  ```json
  "overrides": {
    "<package>": "<safe-version>"
  }
  ```
  Then run `npm install`

  **Important**: use `overrides` only when multiple versions of the package are present and we cannot align them only using `npm install`

Use https://www.npmjs.com/ to verify the safe version exists and pick the latest patch if possible.

## Verify

```shell
npm ci
npm audit --json
```

- Confirm the CVE no longer appears in `npm audit`
- Use `npm list '<package>'` to confirm the resolved version
- Use `grep -r '<package>' --include='package.json' -l` to find all workspace `package.json` files that declare the package
- Verify each declared version range has a minimum that is >= the safe version (e.g. `^1.15.0`, not `^1.13.5`)
- If any declared range still includes vulnerable versions, update it and re-run `npm install`
