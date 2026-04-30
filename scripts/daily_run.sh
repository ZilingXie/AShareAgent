#!/usr/bin/env bash
set -euo pipefail

if ! command -v uv >/dev/null 2>&1; then
  echo "uv 未安装或不在 PATH，无法运行 AShareAgent daily-run" >&2
  exit 1
fi

trade_date="${1:-$(date +%F)}"
uv run ashare daily-run --trade-date "${trade_date}"
