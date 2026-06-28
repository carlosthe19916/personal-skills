#!/usr/bin/env bash
# Create, list, and remove sibling git worktrees for GitHub PRs and GitLab MRs.
#
# Worktree directory: {repo_basename}.{number}  (e.g. my-app.123)
# Local branch: pr-{number} (GitHub) or mr-{number} (GitLab)
#
# Usage:
#   pr_worktree.sh checkout [--force] <number-or-url>
#   pr_worktree.sh list [--path PATH]
#   pr_worktree.sh remove [--path PATH] [--force] <number>
#
# Requires: git, jq; gh and/or glab for auth preflight when needed

set -euo pipefail

FORCE=false
REPO_PATH=""

usage() {
  cat >&2 <<EOF
Usage: pr_worktree.sh checkout [--force] <number-or-url>
       pr_worktree.sh list [--path PATH]
       pr_worktree.sh remove [--path PATH] [--force] <number>

Worktree path: \$(dirname repo)/\$(basename repo).\${NUMBER}
Example: /home/user/git/my-app + 123 -> /home/user/git/my-app.123
EOF
  exit 1
}

normalize_gitlab_host() {
  local host="$1"
  host="${host#https://}"
  host="${host#http://}"
  host="${host%/}"
  host="${host%%/*}"
  echo "$host"
}

expand_path() {
  local p="$1"
  if [[ "$p" == "~" ]]; then
    echo "$HOME"
  elif [[ "$p" == "~/"* ]]; then
    echo "${HOME}/${p#~/}"
  else
    echo "$p"
  fi
}

resolve_repo_root() {
  local base="${1:-.}"
  base="$(expand_path "$base")"
  if ! git -C "$base" rev-parse --show-toplevel >/dev/null 2>&1; then
    echo "Error: not a git repository: $base" >&2
    echo "Run from inside a clone or pass --path to a local repository." >&2
    exit 1
  fi
  git -C "$base" rev-parse --show-toplevel
}

resolve_fetch_remote() {
  local repo_root="$1"
  if git -C "$repo_root" remote get-url origin >/dev/null 2>&1; then
    echo "origin"
    return 0
  fi
  local first
  first="$(git -C "$repo_root" remote | head -1)"
  if [[ -n "$first" ]]; then
    echo "$first"
    return 0
  fi
  echo "Error: no git remote configured in $repo_root" >&2
  exit 1
}

remote_url() {
  local repo_root="$1"
  local remote
  remote="$(resolve_fetch_remote "$repo_root")"
  git -C "$repo_root" remote get-url "$remote" 2>/dev/null || true
}

detect_provider_from_origin() {
  local url="$1"
  local host=""
  url="${url,,}"

  if [[ "$url" =~ (^|[/@])github\.com[:/] ]] || [[ "$url" =~ ^git@github\.com: ]]; then
    echo "github"
    return 0
  fi

  if [[ "$url" =~ ^git@([^:]+): ]]; then
    host="${BASH_REMATCH[1]}"
    if [[ "$host" == *github* ]]; then
      echo "github"
      return 0
    fi
    if [[ "$host" == *gitlab* ]]; then
      echo "gitlab"
      return 0
    fi
  fi

  if [[ "$url" =~ ^https?://([^/]+)/ ]]; then
    host="${BASH_REMATCH[1]}"
    if [[ "$host" == *github* ]]; then
      echo "github"
      return 0
    fi
  fi

  if [[ "$url" == *gitlab* ]]; then
    echo "gitlab"
    return 0
  fi

  echo "unknown"
}

gitlab_host_from_origin() {
  local url="$1"
  local identity
  identity="$(gitlab_identity_from_origin "$url")" || return 1
  echo "${identity%%|*}"
}

resolve_provider_context() {
  local repo_root="$1"
  local url provider gitlab_host="gitlab.com"
  url="$(remote_url "$repo_root")"
  [[ -n "$url" ]] || {
    echo "Error: no git remote configured in $repo_root" >&2
    exit 1
  }
  provider="$(detect_provider_from_origin "$url")"
  if [[ "$provider" == "unknown" ]]; then
    echo "Error: remote must be GitHub or GitLab (got: $url)" >&2
    exit 1
  fi
  if [[ "$provider" == "gitlab" ]]; then
    gitlab_host="$(gitlab_host_from_origin "$url")" || {
      echo "Error: could not parse GitLab host from remote: $url" >&2
      exit 1
    }
  fi
  echo "${provider}|${gitlab_host}"
}

github_repo_from_origin() {
  local url="$1"
  if [[ "$url" =~ github\.com[:/]([^/]+/[^/.]+)(\.git)?$ ]]; then
    echo "${BASH_REMATCH[1]}"
    return 0
  fi
  if [[ "$url" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)? ]]; then
    echo "${BASH_REMATCH[1]}/${BASH_REMATCH[2]}"
    return 0
  fi
  if [[ "$url" =~ ^git@([^:]+):([^/]+/[^/]+?)(\.git)?$ ]] && [[ "${BASH_REMATCH[1],,}" == *github* ]]; then
    echo "${BASH_REMATCH[2]%.git}"
    return 0
  fi
  if [[ "$url" =~ ^https?://[^/]*github[^/]*/([^/]+/[^/]+?)(\.git)?/?$ ]]; then
    echo "${BASH_REMATCH[1]%.git}"
    return 0
  fi
  return 1
}

gitlab_identity_from_origin() {
  local url="$1"
  local host path
  if [[ "$url" =~ ^git@([^:]+):(.+?)(\.git)?$ ]]; then
    host="${BASH_REMATCH[1]}"
    path="${BASH_REMATCH[2]%.git}"
    echo "$(normalize_gitlab_host "$host")|$path"
    return 0
  fi
  if [[ "$url" =~ ^https?://([^/]+)/(.+?)(\.git)?/?$ ]]; then
    host="${BASH_REMATCH[1]}"
    path="${BASH_REMATCH[2]%.git}"
    echo "$(normalize_gitlab_host "$host")|$path"
    return 0
  fi
  return 1
}

local_branch_name() {
  local provider="$1"
  local number="$2"
  if [[ "$provider" == "github" ]]; then
    echo "pr-${number}"
  else
    echo "mr-${number}"
  fi
}

worktree_path_for() {
  local repo_root="$1"
  local number="$2"
  local repo_name parent
  repo_name="$(basename "$repo_root")"
  parent="$(dirname "$repo_root")"
  echo "${parent}/${repo_name}.${number}"
}

parse_checkout_arg() {
  local arg="$1"
  local provider="" number="" github_repo="" gitlab_host="" gitlab_path=""

  if [[ "$arg" =~ ^[0-9]+$ ]]; then
    number="$arg"
    echo "number|${number}"
    return 0
  fi

  if [[ "$arg" =~ ^https?://[^/]*github[^/]*/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
    github_repo="${BASH_REMATCH[1]%.git}"
    number="${BASH_REMATCH[2]}"
    echo "github|${number}|${github_repo}"
    return 0
  fi

  if [[ "$arg" =~ github\.com/([^/]+/[^/]+)/pull/([0-9]+) ]]; then
    github_repo="${BASH_REMATCH[1]%.git}"
    number="${BASH_REMATCH[2]}"
    echo "github|${number}|${github_repo}"
    return 0
  fi

  if [[ "$arg" =~ ^https?://([^/]+)/(.+)/-/merge_requests/([0-9]+) ]]; then
    gitlab_host="$(normalize_gitlab_host "${BASH_REMATCH[1]}")"
    gitlab_path="${BASH_REMATCH[2]%.git}"
    number="${BASH_REMATCH[3]}"
    echo "gitlab|${number}|${gitlab_host}|${gitlab_path}"
    return 0
  fi

  echo "Error: expected a PR/MR number or full GitHub/GitLab URL, got: $arg" >&2
  exit 1
}

validate_repo_match() {
  local repo_root="$1"
  local parsed_kind="$2"
  shift 2
  local origin
  origin="$(remote_url "$repo_root")"
  [[ -n "$origin" ]] || {
    echo "Error: no git remote configured in $repo_root" >&2
    exit 1
  }

  case "$parsed_kind" in
    number)
      return 0
      ;;
    github)
      local expected="$1"
      local actual
      actual="$(github_repo_from_origin "$origin" || true)"
      if [[ "$actual" != "$expected" ]]; then
        echo "Error: URL is for GitHub repo '$expected' but origin is '${actual:-unknown}'." >&2
        echo "Run /pr-checkout from the matching clone." >&2
        exit 1
      fi
      ;;
    gitlab)
      local expected_host="$1"
      local expected_path="$2"
      local identity host path
      identity="$(gitlab_identity_from_origin "$origin" || true)"
      if [[ -z "$identity" ]]; then
        echo "Error: could not parse GitLab identity from origin: $origin" >&2
        exit 1
      fi
      IFS='|' read -r host path <<<"$identity"
      if [[ "$host" != "$expected_host" ]] || [[ "$path" != "$expected_path" ]]; then
        echo "Error: URL is for GitLab ${expected_host}/${expected_path} but origin is ${host}/${path}." >&2
        exit 1
      fi
      ;;
  esac
}

preflight_auth() {
  local provider="$1"
  local gitlab_host="${2:-gitlab.com}"
  case "$provider" in
    github)
      if command -v gh >/dev/null 2>&1 && ! gh auth status >/dev/null 2>&1; then
        echo "Error: gh is not authenticated. Run: gh auth login" >&2
        exit 1
      fi
      ;;
    gitlab)
      if command -v glab >/dev/null 2>&1 && ! glab auth status --hostname "$gitlab_host" >/dev/null 2>&1; then
        echo "Error: glab is not authenticated for ${gitlab_host}." >&2
        echo "Run: glab auth login --hostname ${gitlab_host}" >&2
        exit 1
      fi
      ;;
  esac
}

worktree_registered() {
  local repo_root="$1"
  local wt_path="$2"
  git -C "$repo_root" worktree list --porcelain | awk -v p="$wt_path" '
    $1 == "worktree" && $2 == p { found=1 }
    END { exit !found }
  '
}

is_managed_worktree_path() {
  local repo_root="$1"
  local wt_path="$2"

  if worktree_registered "$repo_root" "$wt_path"; then
    return 0
  fi
  if [[ -f "$wt_path/.git" ]]; then
    local gitfile
    gitfile="$(head -1 "$wt_path/.git" 2>/dev/null || true)"
    [[ "$gitfile" == gitdir:* ]] && return 0
  fi
  return 1
}

delete_local_branch_if_safe() {
  local repo_root="$1"
  local branch="$2"

  if ! git -C "$repo_root" show-ref --verify --quiet "refs/heads/${branch}"; then
    return 0
  fi
  if git -C "$repo_root" branch -D "$branch" >/dev/null 2>&1; then
    return 0
  fi
  echo "Error: could not delete branch ${branch} (checked out elsewhere?)" >&2
  exit 1
}

remove_worktree_if_exists() {
  local repo_root="$1"
  local wt_path="$2"
  local branch="$3"

  if worktree_registered "$repo_root" "$wt_path"; then
    git -C "$repo_root" worktree remove --force "$wt_path"
  elif [[ -e "$wt_path" ]]; then
    if is_managed_worktree_path "$repo_root" "$wt_path"; then
      git -C "$repo_root" worktree remove --force "$wt_path" 2>/dev/null || rm -rf "$wt_path"
    else
      echo "Error: ${wt_path} exists but is not a worktree for this repository." >&2
      echo "Move or remove it manually before retrying." >&2
      exit 1
    fi
  fi

  delete_local_branch_if_safe "$repo_root" "$branch"
}

ensure_branch_available_for_fetch() {
  local repo_root="$1"
  local branch="$2"

  if ! git -C "$repo_root" show-ref --verify --quiet "refs/heads/${branch}"; then
    return 0
  fi
  if $FORCE; then
    delete_local_branch_if_safe "$repo_root" "$branch"
    return 0
  fi
  echo "Error: branch ${branch} already exists." >&2
  echo "Use --force to replace it, or: /pr-checkout remove ${branch#*-}" >&2
  exit 1
}

cmd_checkout() {
  local arg="${1:-}"
  [[ -n "$arg" ]] || {
    echo "Error: checkout requires a PR/MR number or URL" >&2
    usage
  }

  local repo_root
  repo_root="$(resolve_repo_root ".")"

  local parsed kind
  parsed="$(parse_checkout_arg "$arg")"
  IFS='|' read -r kind rest <<<"$parsed"

  local number provider local_branch worktree_path fetch_remote
  local gitlab_host="gitlab.com"
  local ctx url

  case "$kind" in
    number)
      number="$rest"
      ctx="$(resolve_provider_context "$repo_root")"
      IFS='|' read -r provider gitlab_host <<<"$ctx"
      validate_repo_match "$repo_root" "number"
      ;;
    github)
      number="${rest%%|*}"
      local expected_repo="${rest#*|}"
      provider="github"
      validate_repo_match "$repo_root" "github" "$expected_repo"
      ;;
    gitlab)
      IFS='|' read -r number gitlab_host expected_path <<<"$rest"
      provider="gitlab"
      validate_repo_match "$repo_root" "gitlab" "$gitlab_host" "$expected_path"
      ;;
  esac

  preflight_auth "$provider" "$gitlab_host"

  local_branch="$(local_branch_name "$provider" "$number")"
  worktree_path="$(worktree_path_for "$repo_root" "$number")"
  fetch_remote="$(resolve_fetch_remote "$repo_root")"
  url="$(remote_url "$repo_root")"

  if [[ -e "$worktree_path" ]] || worktree_registered "$repo_root" "$worktree_path"; then
    if ! $FORCE; then
      echo "Error: worktree already exists at $worktree_path" >&2
      echo "Use --force to remove and recreate, or: /pr-checkout remove ${number}" >&2
      exit 1
    fi
    remove_worktree_if_exists "$repo_root" "$worktree_path" "$local_branch"
  fi

  ensure_branch_available_for_fetch "$repo_root" "$local_branch"

  local fetch_ref created=true
  cd "$repo_root"
  if [[ "$provider" == "github" ]]; then
    fetch_ref="pull/${number}/head"
  else
    fetch_ref="merge-requests/${number}/head"
  fi

  if ! git fetch "$fetch_remote" "${fetch_ref}:${local_branch}"; then
    echo "Error: git fetch failed for ${fetch_remote} ${fetch_ref}" >&2
    exit 1
  fi

  if ! git worktree add "$worktree_path" "$local_branch"; then
    echo "Error: git worktree add failed" >&2
    git branch -D "$local_branch" >/dev/null 2>&1 || true
    exit 1
  fi

  local cd_command="cd ${worktree_path}"
  local repo_label
  if [[ "$provider" == "github" ]]; then
    repo_label="$(github_repo_from_origin "$url" 2>/dev/null || basename "$repo_root")"
  else
    repo_label="$(gitlab_identity_from_origin "$url" 2>/dev/null | cut -d'|' -f2 || basename "$repo_root")"
  fi

  cat >&2 <<EOF
Worktree ready: ${worktree_path}  (branch ${local_branch})

  ${cd_command}
EOF

  jq -n \
    --arg repo_root "$repo_root" \
    --arg provider "$provider" \
    --argjson number "$number" \
    --arg branch "$local_branch" \
    --arg worktree_path "$worktree_path" \
    --arg cd_command "$cd_command" \
    --arg repo "$repo_label" \
    --argjson created "$created" \
    '{
      repo_root: $repo_root,
      provider: $provider,
      number: $number,
      repo: $repo,
      branch: $branch,
      worktree_path: $worktree_path,
      cd_command: $cd_command,
      created: $created
    }'
}

cmd_list() {
  local repo_root
  if [[ -n "$REPO_PATH" ]]; then
    repo_root="$(resolve_repo_root "$REPO_PATH")"
  else
    repo_root="$(resolve_repo_root ".")"
  fi

  local repo_name parent
  repo_name="$(basename "$repo_root")"
  parent="$(dirname "$repo_root")"

  local json_items="[]"
  local current_path="" current_branch="" current_head=""

  flush_worktree() {
    if [[ -z "$current_path" ]]; then
      return
    fi
    json_items="$(append_list_item "$json_items" "$repo_root" "$repo_name" "$current_path" "$current_branch" "$current_head")"
    current_path=""
    current_branch=""
    current_head=""
  }

  while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" == worktree\ * ]]; then
      flush_worktree
      current_path="${line#worktree }"
    elif [[ "$line" == branch\ * ]]; then
      current_branch="${line#branch }"
      current_branch="${current_branch#refs/heads/}"
    elif [[ "$line" == HEAD\ * ]]; then
      current_head="${line#HEAD }"
    elif [[ -z "$line" ]]; then
      flush_worktree
    fi
  done < <(git -C "$repo_root" worktree list --porcelain; echo)

  flush_worktree

  jq -n \
    --arg repo_root "$repo_root" \
    --arg repo_name "$repo_name" \
    --argjson worktrees "$json_items" \
    '{repo_root: $repo_root, repo_name: $repo_name, worktrees: $worktrees}'
}

append_list_item() {
  local arr="$1" repo_root="$2" repo_name="$3" wt_path="$4" branch="$5" head="$6"
  local parent expected_prefix number provider prmr cd_command dir_name head_short

  parent="$(dirname "$repo_root")"
  expected_prefix="${parent}/${repo_name}."

  if [[ "$wt_path" != "${expected_prefix}"* ]]; then
    echo "$arr"
    return
  fi

  dir_name="$(basename "$wt_path")"
  if [[ "$branch" =~ ^pr-([0-9]+)$ ]]; then
    number="${BASH_REMATCH[1]}"
    provider="github"
    prmr="PR #${number}"
  elif [[ "$branch" =~ ^mr-([0-9]+)$ ]]; then
    number="${BASH_REMATCH[1]}"
    provider="gitlab"
    prmr="MR !${number}"
  else
    number="${dir_name#${repo_name}.}"
    if [[ ! "$number" =~ ^[0-9]+$ ]]; then
      echo "$arr"
      return
    fi
    provider="unknown"
    prmr="#${number}"
  fi

  cd_command="cd ${wt_path}"
  head_short="${head:0:7}"

  jq \
    --arg worktree_path "$wt_path" \
    --arg directory "$dir_name" \
    --arg branch "$branch" \
    --arg provider "$provider" \
    --arg prmr "$prmr" \
    --argjson number "$number" \
    --arg head "$head_short" \
    --arg cd_command "$cd_command" \
    '. + [{
      worktree_path: $worktree_path,
      directory: $directory,
      branch: $branch,
      provider: $provider,
      number: $number,
      prmr: $prmr,
      head: $head,
      cd_command: $cd_command
    }]' <<<"$arr"
}

cmd_remove() {
  local number="${1:-}"
  [[ -n "$number" ]] || {
    echo "Error: remove requires a PR/MR number" >&2
    usage
  }
  [[ "$number" =~ ^[0-9]+$ ]] || {
    echo "Error: remove target must be a number (e.g. 123)" >&2
    exit 1
  }

  local repo_root
  if [[ -n "$REPO_PATH" ]]; then
    repo_root="$(resolve_repo_root "$REPO_PATH")"
  else
    repo_root="$(resolve_repo_root ".")"
  fi

  local provider ctx gitlab_host="gitlab.com"
  ctx="$(resolve_provider_context "$repo_root")"
  IFS='|' read -r provider gitlab_host <<<"$ctx"

  local local_branch worktree_path
  local_branch="$(local_branch_name "$provider" "$number")"
  worktree_path="$(worktree_path_for "$repo_root" "$number")"

  local has_worktree=false
  if worktree_registered "$repo_root" "$worktree_path" || [[ -d "$worktree_path" ]]; then
    has_worktree=true
  fi
  if ! $has_worktree && ! git -C "$repo_root" show-ref --verify --quiet "refs/heads/${local_branch}"; then
    echo "Error: no worktree at $worktree_path" >&2
    exit 1
  fi

  if $has_worktree; then
    if [[ -e "$worktree_path" ]] && ! is_managed_worktree_path "$repo_root" "$worktree_path"; then
      if ! $FORCE; then
        echo "Error: ${worktree_path} exists but is not a worktree for this repository." >&2
        echo "Use --force only after moving or removing that path manually." >&2
        exit 1
      fi
      echo "Error: refusing to --force remove unrelated directory ${worktree_path}" >&2
      exit 1
    fi
    remove_worktree_if_exists "$repo_root" "$worktree_path" "$local_branch"
  else
    delete_local_branch_if_safe "$repo_root" "$local_branch"
  fi

  jq -n \
    --arg repo_root "$repo_root" \
    --argjson number "$number" \
    --arg branch "$local_branch" \
    --arg worktree_path "$worktree_path" \
    --arg provider "$provider" \
    --argjson removed true \
    '{
      repo_root: $repo_root,
      number: $number,
      branch: $branch,
      worktree_path: $worktree_path,
      provider: $provider,
      removed: $removed
    }'
}

# --- main ---

run_main() {
if [[ $# -lt 1 ]]; then
  usage
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "Error: jq is not installed" >&2
  exit 1
fi

SUBCMD="$1"
shift

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=true
      shift
      ;;
    --path)
      REPO_PATH="${2:-}"
      [[ -n "$REPO_PATH" ]] || usage
      shift 2
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

case "$SUBCMD" in
  checkout)
    cmd_checkout "${1:-}"
    ;;
  list)
    if [[ $# -gt 0 ]]; then
      echo "Error: unexpected arguments for list" >&2
      usage
    fi
    cmd_list
    ;;
  remove)
    cmd_remove "${1:-}"
    ;;
  *)
    echo "Unknown subcommand: $SUBCMD" >&2
    usage
    ;;
esac
}

if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  run_main "$@"
fi
