from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import cast


def write_markdown_report(
    report_root: Path,
    trade_date: str,
    filename: str,
    sections: Mapping[str, object],
) -> Path:
    report_dir = report_root / trade_date
    report_dir.mkdir(parents=True, exist_ok=True)
    path = report_dir / filename
    lines = [f"# {filename}", ""]
    for title, content in sections.items():
        lines.extend([f"## {title}", ""])
        if isinstance(content, list):
            items = cast(list[object], content)
            if content:
                lines.extend([f"- {item}" for item in items])
            else:
                lines.append("- 无")
        else:
            lines.append(str(content))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
