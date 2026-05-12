from __future__ import annotations

import argparse
import os
import plistlib
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEDULED_SLOTS: tuple[tuple[str, int, int], ...] = (
    ("morning_collect", 8, 30),
    ("pre_market_brief", 9, 0),
    ("intraday_decision", 10, 0),
    ("close_collect", 15, 15),
    ("post_market_brief", 16, 0),
)

PROTECTED_USER_DIRS = ("Desktop", "Documents", "Downloads")
APP_SUPPORT_DIRNAME = "AShareAgent"
LAUNCHD_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
DEFAULT_UV_CACHE_DIR = "/private/tmp/ashareagent-uv-cache"
RUNTIME_EXCLUDE_NAMES = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
    "reports",
}


@dataclass(frozen=True)
class LaunchdInstallation:
    repo_root: Path
    home: Path
    app_support_root: Path
    execution_root: Path
    runner: Path
    launch_agents_dir: Path
    log_dir: Path
    requires_runtime_copy: bool


def build_launchd_installation(
    *,
    repo_root: Path,
    home: Path | None = None,
) -> LaunchdInstallation:
    resolved_home = (home or Path.home()).expanduser().resolve(strict=False)
    resolved_repo_root = repo_root.expanduser().resolve(strict=False)
    app_support_root = (
        resolved_home / "Library" / "Application Support" / APP_SUPPORT_DIRNAME
    )
    runtime_root = app_support_root / "runtime"
    requires_runtime_copy = is_under_macos_protected_user_dir(
        resolved_repo_root,
        home=resolved_home,
    )
    execution_root = runtime_root if requires_runtime_copy else resolved_repo_root
    return LaunchdInstallation(
        repo_root=resolved_repo_root,
        home=resolved_home,
        app_support_root=app_support_root,
        execution_root=execution_root,
        runner=execution_root / "scripts" / "scheduled_run.sh",
        launch_agents_dir=resolved_home / "Library" / "LaunchAgents",
        log_dir=resolved_home / "Library" / "Logs" / APP_SUPPORT_DIRNAME,
        requires_runtime_copy=requires_runtime_copy,
    )


def is_under_macos_protected_user_dir(path: Path, *, home: Path) -> bool:
    resolved_path = path.expanduser().resolve(strict=False)
    resolved_home = home.expanduser().resolve(strict=False)
    for dirname in PROTECTED_USER_DIRS:
        protected_root = (resolved_home / dirname).resolve(strict=False)
        if resolved_path == protected_root or resolved_path.is_relative_to(protected_root):
            return True
    return False


def render_plist_payload(
    *,
    installation: LaunchdInstallation,
    slot: str,
    hour: int,
    minute: int,
) -> dict[str, Any]:
    label = _label_for_slot(slot)
    return {
        "Label": label,
        "ProgramArguments": ["/bin/bash", str(installation.runner), slot],
        "WorkingDirectory": str(installation.execution_root),
        "StandardOutPath": str(installation.log_dir / f"{slot}.out.log"),
        "StandardErrorPath": str(installation.log_dir / f"{slot}.err.log"),
        "EnvironmentVariables": {
            "PATH": LAUNCHD_PATH,
            "UV_CACHE_DIR": DEFAULT_UV_CACHE_DIR,
        },
        "StartCalendarInterval": [
            {"Weekday": weekday, "Hour": int(hour), "Minute": int(minute)}
            for weekday in range(1, 6)
        ],
    }


def install_launchd_schedules(
    *,
    repo_root: Path,
    home: Path | None = None,
    dry_run: bool = False,
) -> LaunchdInstallation:
    installation = build_launchd_installation(repo_root=repo_root, home=home)
    _prepare_runtime_if_needed(installation)
    installation.launch_agents_dir.mkdir(parents=True, exist_ok=True)
    installation.log_dir.mkdir(parents=True, exist_ok=True)
    installation.app_support_root.mkdir(parents=True, exist_ok=True)
    installation.app_support_root.chmod(0o700)
    if installation.requires_runtime_copy and installation.execution_root.exists():
        installation.execution_root.chmod(0o700)

    for slot, hour, minute in SCHEDULED_SLOTS:
        label = _label_for_slot(slot)
        plist_path = _write_plist(
            installation=installation,
            slot=slot,
            hour=hour,
            minute=minute,
        )
        if not dry_run:
            _reload_launch_agent(label=label, plist_path=plist_path)
        print(f"installed {label} -> {plist_path}")

    if installation.requires_runtime_copy:
        print(
            "launchd runtime copy: "
            f"{installation.repo_root} -> {installation.execution_root}"
        )
    print(f"AShareAgent launchd schedules installed. Logs: {installation.log_dir}")
    return installation


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Install AShareAgent launchd schedules.")
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument(
        "--home",
        type=Path,
        default=Path.home(),
        help="User home directory; mainly for tests.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=os.getenv("ASHARE_LAUNCHD_DRY_RUN") == "1",
        help="Render plists and runtime copy without calling launchctl.",
    )
    args = parser.parse_args(argv)
    install_launchd_schedules(
        repo_root=args.repo_root,
        home=args.home,
        dry_run=args.dry_run,
    )


def _prepare_runtime_if_needed(installation: LaunchdInstallation) -> None:
    if not installation.requires_runtime_copy:
        _ensure_runner_executable(installation.runner)
        return
    _copy_repo_to_runtime(installation)
    _ensure_runner_executable(installation.runner)


def _copy_repo_to_runtime(installation: LaunchdInstallation) -> None:
    runtime_root = installation.execution_root
    if not runtime_root.is_relative_to(installation.app_support_root):
        raise ValueError("launchd runtime root 必须位于 Application Support 目录下")
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        installation.repo_root,
        runtime_root,
        ignore=_runtime_ignore,
        symlinks=True,
    )


def _runtime_ignore(_directory: str, names: list[str]) -> set[str]:
    return {name for name in names if name in RUNTIME_EXCLUDE_NAMES}


def _ensure_runner_executable(runner: Path) -> None:
    if not runner.exists():
        raise FileNotFoundError(f"找不到 scheduled-run 脚本: {runner}")
    mode = runner.stat().st_mode
    runner.chmod(
        mode
        | stat.S_IXUSR
        | stat.S_IXGRP
        | stat.S_IXOTH,
    )


def _write_plist(
    *,
    installation: LaunchdInstallation,
    slot: str,
    hour: int,
    minute: int,
) -> Path:
    plist_path = installation.launch_agents_dir / f"{_label_for_slot(slot)}.plist"
    payload = render_plist_payload(
        installation=installation,
        slot=slot,
        hour=hour,
        minute=minute,
    )
    plist_path.write_bytes(plistlib.dumps(payload, sort_keys=False))
    return plist_path


def _reload_launch_agent(*, label: str, plist_path: Path) -> None:
    domain = f"gui/{os.getuid()}"
    service = f"{domain}/{label}"
    status = subprocess.run(
        ["/bin/launchctl", "print", service],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if status.returncode == 0:
        subprocess.run(
            ["/bin/launchctl", "bootout", domain, str(plist_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    subprocess.run(["/bin/launchctl", "bootstrap", domain, str(plist_path)], check=True)
    subprocess.run(["/bin/launchctl", "enable", service], check=True)


def _label_for_slot(slot: str) -> str:
    return f"com.xieziling.ashareagent.{slot}"


if __name__ == "__main__":
    main()
