#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
runner="${repo_root}/scripts/scheduled_run.sh"
launch_agents_dir="${HOME}/Library/LaunchAgents"
log_dir="${HOME}/Library/Logs/AShareAgent"

mkdir -p "${launch_agents_dir}" "${log_dir}"

if [[ ! -x "${runner}" ]]; then
  chmod +x "${runner}"
fi

write_plist() {
  local slot="$1"
  local hour="$2"
  local minute="$3"
  local label="com.xieziling.ashareagent.${slot}"
  local plist="${launch_agents_dir}/${label}.plist"
  local stdout_log="${log_dir}/${slot}.out.log"
  local stderr_log="${log_dir}/${slot}.err.log"

  /usr/bin/python3 - "${plist}" "${label}" "${runner}" "${slot}" "${repo_root}" \
    "${stdout_log}" "${stderr_log}" "${hour}" "${minute}" <<'PY'
import plistlib
import sys
from pathlib import Path

plist_path, label, runner, slot, repo_root, stdout_log, stderr_log, hour, minute = sys.argv[1:]
payload = {
    "Label": label,
    "ProgramArguments": ["/bin/bash", runner, slot],
    "WorkingDirectory": repo_root,
    "StandardOutPath": stdout_log,
    "StandardErrorPath": stderr_log,
    "StartCalendarInterval": [
        {"Weekday": weekday, "Hour": int(hour), "Minute": int(minute)}
        for weekday in range(2, 7)
    ],
}
Path(plist_path).write_bytes(plistlib.dumps(payload, sort_keys=False))
PY

  if /bin/launchctl print "gui/$(id -u)/${label}" >/dev/null 2>&1; then
    /bin/launchctl bootout "gui/$(id -u)" "${plist}" >/dev/null 2>&1 || true
  fi
  /bin/launchctl bootstrap "gui/$(id -u)" "${plist}"
  /bin/launchctl enable "gui/$(id -u)/${label}"
  echo "installed ${label} -> ${plist}"
}

write_plist "morning_collect" 8 30
write_plist "pre_market_brief" 9 0
write_plist "intraday_decision" 10 0
write_plist "close_collect" 15 15
write_plist "post_market_brief" 16 0

echo "AShareAgent launchd schedules installed. Logs: ${log_dir}"
