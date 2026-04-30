from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

import pytest
import yaml

from ashare_agent.agents.announcement_analyzer import AnnouncementAnalyzer
from ashare_agent.domain import AnnouncementItem

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "announcement_golden_cases.yml"
TRADE_DATE = date(2026, 4, 29)
PUBLISHED_AT = datetime(2026, 4, 29, 8, 30)
COLLECTED_AT = datetime(2026, 4, 29, 8, 35)


class ExpectedCase(TypedDict):
    category: str
    sentiment: Literal["positive", "neutral", "negative"]
    is_material: bool
    exclude: bool
    reason_keywords: list[str]


class GoldenCase(TypedDict):
    case_id: str
    scenario: str
    symbol: str
    name: str
    title: str
    source_category: str
    expected: ExpectedCase


def _load_golden_cases() -> list[GoldenCase]:
    raw_cases = yaml.safe_load(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert isinstance(raw_cases, list)
    return cast(list[GoldenCase], raw_cases)


GOLDEN_CASES = _load_golden_cases()


def _item_from_case(case: GoldenCase) -> AnnouncementItem:
    return AnnouncementItem(
        symbol=case["symbol"],
        name=case["name"],
        title=case["title"],
        category=case["source_category"],
        published_at=PUBLISHED_AT,
        url=f"https://example.test/{case['case_id']}",
        source="golden",
        trade_date=TRADE_DATE,
        collected_at=COLLECTED_AT,
    )


def _case_id(case: GoldenCase) -> str:
    return case["case_id"]


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


@pytest.mark.parametrize("case", GOLDEN_CASES, ids=_case_id)
def test_announcement_analyzer_matches_golden_case(case: GoldenCase) -> None:
    event = AnnouncementAnalyzer().analyze([_item_from_case(case)])[0]
    expected = case["expected"]

    assert event.category == expected["category"], case["case_id"]
    assert event.sentiment == expected["sentiment"], case["case_id"]
    assert event.is_material is expected["is_material"], case["case_id"]
    assert event.exclude is expected["exclude"], case["case_id"]
    joined_reasons = " ".join(event.reasons)
    for keyword in expected["reason_keywords"]:
        assert keyword in joined_reasons, case["case_id"]
