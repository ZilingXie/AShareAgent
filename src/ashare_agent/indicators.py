from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from ashare_agent.domain import MarketBar, TechnicalIndicator


def _mean(values: list[Decimal]) -> Decimal:
    if not values:
        return Decimal("0")
    return sum(values, Decimal("0")) / Decimal(len(values))


def _return_pct(current: Decimal, previous: Decimal) -> float:
    if previous == 0:
        return 0.0
    return float((current - previous) / previous)


def calculate_indicators(trade_date: date, bars: list[MarketBar]) -> list[TechnicalIndicator]:
    grouped: dict[str, list[MarketBar]] = defaultdict(list)
    for bar in bars:
        grouped[bar.symbol].append(bar)

    indicators: list[TechnicalIndicator] = []
    for symbol, symbol_bars in grouped.items():
        ordered = sorted(symbol_bars, key=lambda item: item.trade_date)
        if not ordered:
            continue
        latest = ordered[-1]
        closes = [bar.close for bar in ordered]
        volumes = [Decimal(bar.volume) for bar in ordered]
        ma5 = _mean(closes[-5:])
        ma20 = _mean(closes[-20:])
        avg_volume = _mean(volumes[-20:])
        previous_5 = closes[-6] if len(closes) >= 6 else closes[0]
        previous_20 = closes[-21] if len(closes) >= 21 else closes[0]
        volume_ratio = float(Decimal(latest.volume) / avg_volume) if avg_volume > 0 else 0.0
        indicators.append(
            TechnicalIndicator(
                symbol=symbol,
                trade_date=trade_date,
                close_above_ma5=latest.close > ma5,
                close_above_ma20=latest.close > ma20,
                return_5d=_return_pct(latest.close, previous_5),
                return_20d=_return_pct(latest.close, previous_20),
                volume_ratio=volume_ratio,
            )
        )
    return indicators

