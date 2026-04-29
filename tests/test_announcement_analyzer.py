from __future__ import annotations

from datetime import date, datetime

from ashare_agent.agents.announcement_analyzer import AnnouncementAnalyzer
from ashare_agent.domain import AnnouncementItem


def test_announcement_analyzer_classifies_material_positive_and_exclusion() -> None:
    analyzer = AnnouncementAnalyzer()
    items = [
        AnnouncementItem(
            symbol="510300",
            name="沪深300ETF",
            title="基金规模增长并提高分红比例的公告",
            category="重大事项",
            published_at=datetime(2026, 4, 29, 8, 30),
            url="https://example.test/a",
            source="mock",
            trade_date=date(2026, 4, 29),
            collected_at=datetime(2026, 4, 29, 8, 35),
        ),
        AnnouncementItem(
            symbol="600000",
            name="样本银行",
            title="关于重大诉讼及退市风险提示的公告",
            category="风险提示",
            published_at=datetime(2026, 4, 29, 8, 30),
            url="https://example.test/b",
            source="mock",
            trade_date=date(2026, 4, 29),
            collected_at=datetime(2026, 4, 29, 8, 35),
        ),
    ]

    events = analyzer.analyze(items)

    assert events[0].sentiment == "positive"
    assert events[0].is_material is True
    assert events[0].exclude is False
    assert events[1].sentiment == "negative"
    assert events[1].exclude is True
    assert "风险" in events[1].reasons[0]

