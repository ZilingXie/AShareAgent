#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:${PATH:-}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/private/tmp/ashareagent-uv-cache}"

slot="${1:-}"
trade_date="${2:-$(TZ=Asia/Shanghai date +%F)}"

if [[ -z "${slot}" ]]; then
  echo "用法: scripts/scheduled_run.sh <slot> [YYYY-MM-DD]" >&2
  exit 2
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${repo_root}"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv 未安装或不在 PATH，无法运行 AShareAgent scheduled-run" >&2
  exit 1
fi

uv run ashare scheduled-run --slot "${slot}" --trade-date "${trade_date}"
