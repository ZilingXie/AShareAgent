#!/usr/bin/env bash
set -euo pipefail

launch_agents_dir="${HOME}/Library/LaunchAgents"
slots=(
  morning_collect
  pre_market_brief
  intraday_decision
  close_collect
  post_market_brief
)

for slot in "${slots[@]}"; do
  label="com.xieziling.ashareagent.${slot}"
  plist="${launch_agents_dir}/${label}.plist"
  if /bin/launchctl print "gui/$(id -u)/${label}" >/dev/null 2>&1; then
    /bin/launchctl bootout "gui/$(id -u)" "${plist}" >/dev/null 2>&1 || true
  fi
  rm -f "${plist}"
  echo "removed ${label}"
done
