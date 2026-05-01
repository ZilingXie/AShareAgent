from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from ashare_agent.config import load_universe
from ashare_agent.providers.akshare_provider import AKShareProvider

pytestmark = pytest.mark.external


@pytest.mark.external_daily
def test_akshare_external_smoke_returns_calendar_and_market_bars() -> None:
    assets = load_universe(Path("configs/universe.yml"), enabled_only=True)
    provider = AKShareProvider(assets[:1])

    calendar = provider.get_trade_calendar()
    bars = provider.get_market_bars(date(2026, 4, 29), lookback_days=2)

    assert calendar
    assert bars


@pytest.mark.external_intraday
@pytest.mark.external_intraday_akshare_em
def test_akshare_external_smoke_returns_eastmoney_intraday_bars() -> None:
    assets = load_universe(Path("configs/universe.yml"), enabled_only=True)
    provider = AKShareProvider(assets[:1], intraday_source="akshare_em")

    intraday_bars = provider.get_intraday_bars(date(2026, 4, 29), [assets[0].symbol])

    assert intraday_bars


@pytest.mark.external_intraday
@pytest.mark.external_intraday_akshare_sina
def test_akshare_external_smoke_returns_sina_intraday_bars() -> None:
    assets = load_universe(Path("configs/universe.yml"), enabled_only=True)
    provider = AKShareProvider(assets[:1], intraday_source="akshare_sina")

    intraday_bars = provider.get_intraday_bars(date(2026, 4, 29), [assets[0].symbol])

    assert intraday_bars
    assert {bar.source for bar in intraday_bars} == {"akshare_sina"}
