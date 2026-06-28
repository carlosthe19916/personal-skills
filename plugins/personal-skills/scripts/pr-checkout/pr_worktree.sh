#!/usr/bin/env bash
# Thin wrapper — logic lives in personal_skills.pr_checkout
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export PYTHONPATH="${ROOT}${PYTHONPATH:+:${PYTHONPATH}}"
exec python3 -m personal_skills.pr_checkout "$@"
