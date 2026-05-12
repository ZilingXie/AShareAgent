from __future__ import annotations

from pathlib import Path

from ashare_agent.launchd_installer import (
    build_launchd_installation,
    install_launchd_schedules,
    render_plist_payload,
)


def test_desktop_repo_uses_application_support_runtime_for_launchd() -> None:
    home = Path("/Users/tester")
    repo_root = home / "Desktop" / "personal_proj" / "AShareAgent"

    installation = build_launchd_installation(repo_root=repo_root, home=home)
    payload = render_plist_payload(
        installation=installation,
        slot="morning_collect",
        hour=8,
        minute=30,
    )

    expected_runtime = home / "Library" / "Application Support" / "AShareAgent" / "runtime"
    assert installation.requires_runtime_copy is True
    assert installation.execution_root == expected_runtime
    assert installation.runner == expected_runtime / "scripts" / "scheduled_run.sh"
    assert payload["WorkingDirectory"] == str(expected_runtime)
    assert payload["ProgramArguments"] == [
        "/bin/bash",
        str(expected_runtime / "scripts" / "scheduled_run.sh"),
        "morning_collect",
    ]


def test_launchd_calendar_interval_uses_monday_to_friday_weekdays() -> None:
    home = Path("/Users/tester")
    repo_root = home / "Projects" / "AShareAgent"
    installation = build_launchd_installation(repo_root=repo_root, home=home)

    payload = render_plist_payload(
        installation=installation,
        slot="close_collect",
        hour=15,
        minute=15,
    )

    intervals = payload["StartCalendarInterval"]
    assert [item["Weekday"] for item in intervals] == [1, 2, 3, 4, 5]


def test_unprotected_repo_can_be_used_directly_by_launchd() -> None:
    home = Path("/Users/tester")
    repo_root = home / "Projects" / "AShareAgent"

    installation = build_launchd_installation(repo_root=repo_root, home=home)

    assert installation.requires_runtime_copy is False
    assert installation.execution_root == repo_root
    assert installation.runner == repo_root / "scripts" / "scheduled_run.sh"


def test_install_copies_desktop_repo_runtime_and_excludes_generated_files(
    tmp_path: Path,
) -> None:
    home = tmp_path / "home"
    repo_root = home / "Desktop" / "AShareAgent"
    scripts_dir = repo_root / "scripts"
    scripts_dir.mkdir(parents=True)
    (scripts_dir / "scheduled_run.sh").write_text("#!/usr/bin/env bash\n", encoding="utf-8")
    (repo_root / ".env").write_text("DATABASE_URL=postgresql://example\n", encoding="utf-8")
    (repo_root / ".git").write_text("gitdir: ignored\n", encoding="utf-8")
    (repo_root / "reports").mkdir()
    (repo_root / "reports" / "old.md").write_text("old report\n", encoding="utf-8")

    installation = install_launchd_schedules(
        repo_root=repo_root,
        home=home,
        dry_run=True,
    )

    runtime_root = home / "Library" / "Application Support" / "AShareAgent" / "runtime"
    plist_path = (
        home
        / "Library"
        / "LaunchAgents"
        / "com.xieziling.ashareagent.morning_collect.plist"
    )
    plist_content = plist_path.read_bytes()
    assert installation.execution_root == runtime_root
    assert (runtime_root / "scripts" / "scheduled_run.sh").exists()
    assert (runtime_root / ".env").exists()
    assert not (runtime_root / ".git").exists()
    assert not (runtime_root / "reports").exists()
    assert b"Desktop" not in plist_content
    assert bytes(str(runtime_root), encoding="utf-8") in plist_content
