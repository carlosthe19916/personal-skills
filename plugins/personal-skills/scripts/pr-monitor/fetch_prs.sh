#!/usr/bin/env bash
# Fetch open PRs/MRs across GitHub (gh) and GitLab (glab) repos.
# Outputs a normalized JSON array to stdout.
#
# Usage:
#   fetch_prs.sh [flags] [github:owner/repo | gitlab:HOST:group/project | gitlab:group/project | owner/repo ...]
#
# GitLab host-qualified repos: gitlab:gitlab.cee.redhat.com:group/project
# Bare gitlab:group/project uses --gitlab-host or defaults to gitlab.com.
#
# Requires: jq, and gh and/or glab as needed

set -euo pipefail

AUTHOR=""
MODE="ready"
DEFAULT_GITLAB_HOST="gitlab.com"

normalize_gitlab_host() {
  local host="$1"
  host="${host#https://}"
  host="${host#http://}"
  host="${host%/}"
  host="${host%%/*}"
  echo "$host"
}

looks_like_hostname() {
  local candidate="$1"
  [[ "$candidate" == *.* ]] || [[ "$candidate" == "gitlab.com" ]]
}

usage() {
  cat >&2 <<EOF
Usage: fetch_prs.sh [--author LOGIN] [--gitlab-host HOST] [--include-drafts | --wip | --ready] \\
  [github:owner/repo | gitlab:HOST:group/project | gitlab:group/project | owner/repo ...]

Repo prefixes:
  github:owner/repo                  GitHub repository
  gitlab:HOST:group/project          GitLab project on a specific instance
  gitlab:group/project               GitLab project (--gitlab-host or gitlab.com)
EOF
  exit 1
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --author)
      AUTHOR="${2:-}"
      [[ -n "$AUTHOR" ]] || usage
      shift 2
      ;;
    --gitlab-host)
      DEFAULT_GITLAB_HOST="${2:-}"
      [[ -n "$DEFAULT_GITLAB_HOST" ]] || usage
      shift 2
      ;;
    --include-drafts|--all)
      MODE="all"
      shift
      ;;
    --wip)
      MODE="wip"
      shift
      ;;
    --ready)
      MODE="ready"
      shift
      ;;
    -h|--help)
      usage
      ;;
    -*)
      echo "Unknown option: $1" >&2
      usage
      ;;
    *)
      break
      ;;
  esac
done

if [[ $# -lt 1 ]]; then
  echo "Error: at least one repository is required" >&2
  usage
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is not installed" >&2
  exit 1
fi

DEFAULT_GITLAB_HOST="$(normalize_gitlab_host "$DEFAULT_GITLAB_HOST")"

parse_repo() {
  local spec="$1"
  if [[ "$spec" == github:* ]]; then
    echo "github||${spec#github:}"
    return
  fi

  if [[ "$spec" == gitlab:* ]]; then
    local rest="${spec#gitlab:}"
    local host path

    if [[ "$rest" == *:* ]]; then
      local candidate_host="${rest%%:*}"
      local candidate_path="${rest#*:}"
      if looks_like_hostname "$candidate_host" && [[ -n "$candidate_path" ]]; then
        host="$(normalize_gitlab_host "$candidate_host")"
        path="$candidate_path"
        echo "gitlab|${host}|${path}"
        return
      fi
    fi

    host="$(normalize_gitlab_host "$DEFAULT_GITLAB_HOST")"
    path="$rest"
    echo "gitlab|${host}|${path}"
    return
  fi

  echo "github||${spec}"
}

need_github=false
need_gitlab=false
REPOS=()
declare -A GITLAB_HOSTS=()

for spec in "$@"; do
  IFS='|' read -r provider host path <<<"$(parse_repo "$spec")"
  REPOS+=("${provider}|${host}|${path}")
  case "$provider" in
    github) need_github=true ;;
    gitlab)
      need_gitlab=true
      GITLAB_HOSTS["$host"]=1
      ;;
  esac
done

if $need_github; then
  if ! command -v gh >/dev/null 2>&1; then
    echo "Error: gh CLI is required for GitHub repos but is not installed" >&2
    exit 1
  fi
  if ! gh auth status >/dev/null 2>&1; then
    echo "Error: gh is not authenticated. Run: gh auth login" >&2
    exit 1
  fi
fi

if $need_gitlab; then
  if ! command -v glab >/dev/null 2>&1; then
    echo "Error: glab CLI is required for GitLab repos but is not installed" >&2
    exit 1
  fi
  for host in "${!GITLAB_HOSTS[@]}"; do
    if ! glab auth status --hostname "$host" >/dev/null 2>&1; then
      echo "Error: glab is not authenticated for ${host}." >&2
      echo "Run: glab auth login --hostname ${host}" >&2
      exit 1
    fi
  done
fi

PR_JSON='number,title,url,author,isDraft,updatedAt,createdAt,statusCheckRollup,reviews,labels'
TMPDIR="${TMPDIR:-/tmp}"
MERGE_FILE="$(mktemp "${TMPDIR}/pr-monitor-XXXXXX.json")"
echo '[]' >"$MERGE_FILE"

run_glab() {
  local host="$1"
  shift
  GITLAB_HOST="$host" glab "$@"
}

normalize_github_prs() {
  local repo="$1"
  local raw

  if ! raw="$(gh pr list -R "$repo" --state open --limit 100 \
    --json "$PR_JSON" 2>/dev/null)"; then
    echo "Warning: failed to fetch GitHub PRs for $repo" >&2
    return 0
  fi

  jq --arg repo "$repo" '
    def ci_status:
      . as $rollup
      | if ($rollup | length) == 0 then null
        elif any(.[]; (.conclusion // .state // "") | test("FAILURE|ERROR|CANCELLED"; "i")) then "FAILURE"
        elif any(.[]; (.status // "") == "IN_PROGRESS" or (.state // "") == "PENDING") then "PENDING"
        elif all(.[]; (.conclusion // .state // "") | test("SUCCESS|NEUTRAL|SKIPPED"; "i")) then "SUCCESS"
        else "PENDING"
        end;

    map({
      number,
      title,
      url,
      repo: $repo,
      provider: "github",
      instance: null,
      author: (.author.login // "unknown"),
      is_draft: (.isDraft // false),
      is_automated: false,
      created_at: .createdAt,
      updated_at: .updatedAt,
      ci_status: ((.statusCheckRollup // []) | ci_status),
      reviews: {
        count: ((.reviews // []) | length),
        has_new_commits: false
      },
      labels: [(.labels // [])[] | .name],
      unresolved_conversations: 0
    })
  ' <<<"$raw"
}

normalize_gitlab_mrs() {
  local host="$1"
  local repo="$2"
  local raw
  local -a glab_args=(mr list -R "$repo" --output json --per-page 100)

  case "$MODE" in
    ready) glab_args+=(--not-draft) ;;
    wip) glab_args+=(--draft) ;;
  esac

  if [[ -n "$AUTHOR" ]]; then
    glab_args+=(--author "$AUTHOR")
  fi

  if ! raw="$(run_glab "$host" "${glab_args[@]}" 2>/dev/null)"; then
    echo "Warning: failed to fetch GitLab MRs for ${host}/${repo}" >&2
    return 0
  fi

  if [[ -z "$raw" || "$raw" == "[]" || "$raw" == "null" ]]; then
    echo '[]'
    return 0
  fi

  jq --arg repo "$repo" --arg host "$host" '
    map({
      number: .iid,
      title,
      url: .web_url,
      repo: $repo,
      provider: "gitlab",
      instance: $host,
      author: (.author.username // .author.name // "unknown"),
      is_draft: ((.draft // false) or (.work_in_progress // false)),
      is_automated: false,
      created_at: .created_at,
      updated_at: .updated_at,
      ci_status: (
        if .head_pipeline.status then
          (.head_pipeline.status
            | if . == "success" then "SUCCESS"
              elif . == "failed" then "FAILURE"
              elif . == "running" or . == "pending" or . == "created" then "PENDING"
              elif . == "canceled" or . == "cancelled" then "FAILURE"
              else (. | ascii_upcase)
              end)
        else null
        end
      ),
      reviews: {
        count: ((.approved_by // []) | length),
        has_new_commits: false
      },
      labels: (
        if (.labels | type) == "array" then
          [.labels[] | if type == "string" then . else .name end]
        else []
        end
      ),
      unresolved_conversations: 0
    })
  ' <<<"$raw"
}

apply_filters() {
  local json="$1"
  jq --arg author "$AUTHOR" --arg mode "$MODE" '
    (if $author != "" then map(select(.author == $author)) else . end)
    | (if $mode == "wip" then map(select(.is_draft == true))
       elif $mode == "ready" then map(select(.is_draft == false))
       else . end)
  ' <<<"$json"
}

for entry in "${REPOS[@]}"; do
  IFS='|' read -r provider host path <<<"$entry"

  case "$provider" in
    github)
      echo "Fetching github:${path} ..." >&2
      repo_prs="$(normalize_github_prs "$path")"
      ;;
    gitlab)
      echo "Fetching gitlab:${host}:${path} ..." >&2
      repo_prs="$(normalize_gitlab_mrs "$host" "$path")"
      ;;
    *)
      echo "Warning: unknown provider '$provider'" >&2
      continue
      ;;
  esac

  merged="$(jq -s 'add' "$MERGE_FILE" <(echo "$repo_prs"))"
  echo "$merged" >"$MERGE_FILE"
done

apply_filters "$(cat "$MERGE_FILE")"
rm -f "$MERGE_FILE"
