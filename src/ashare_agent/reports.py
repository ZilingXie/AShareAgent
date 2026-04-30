from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast


@dataclass(frozen=True)
class MarkdownTable:
    headers: Sequence[str]
    rows: Sequence[Sequence[object]]


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
        if isinstance(content, MarkdownTable):
            lines.extend(_render_table(content))
        elif isinstance(content, list):
            items = cast(list[object], content)
            if items:
                lines.extend([f"- {item}" for item in items])
            else:
                lines.append("- 无")
        else:
            lines.append(str(content))
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def _render_table(table: MarkdownTable) -> list[str]:
    headers = list(table.headers)
    if not headers:
        raise ValueError("MarkdownTable headers 不能为空")

    lines = [
        "| " + " | ".join(_table_cell(header) for header in headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in table.rows:
        cells = list(row)
        if len(cells) != len(headers):
            raise ValueError("MarkdownTable row 长度必须与 headers 一致")
        lines.append("| " + " | ".join(_table_cell(cell) for cell in cells) + " |")
    return lines


def _table_cell(value: object) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        return "-"
    return text.replace("\n", " ").replace("|", "\\|")
