from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from ashare_agent.domain import MarketBar, MarketRegime


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class MarketRegimeAnalyzer:
    def analyze(self, trade_date: date, bars: list[MarketBar]) -> MarketRegime:
        grouped: dict[str, list[MarketBar]] = defaultdict(list)
        for bar in bars:
            grouped[bar.symbol].append(bar)

        trend_scores: list[float] = []
        volume_scores: list[float] = []
        for symbol_bars in grouped.values():
            ordered = sorted(symbol_bars, key=lambda item: item.trade_date)
            if len(ordered) < 2:
                continue
            first = ordered[0].close
            last = ordered[-1].close
            trend = float((last - first) / first) if first else 0.0
            trend_scores.append(_clamp(0.5 + trend * 4))
            recent_volume = Decimal(sum(bar.volume for bar in ordered[-5:])) / Decimal(
                min(5, len(ordered))
            )
            earlier_volume = Decimal(sum(bar.volume for bar in ordered[:5])) / Decimal(
                min(5, len(ordered))
            )
            volume_ratio = float(recent_volume / earlier_volume) if earlier_volume else 1.0
            volume_scores.append(_clamp(0.5 + (volume_ratio - 1.0) / 2))

        trend_score = sum(trend_scores) / len(trend_scores) if trend_scores else 0.0
        volume_score = sum(volume_scores) / len(volume_scores) if volume_scores else 0.0
        risk_appetite_score = (trend_score * 0.7) + (volume_score * 0.3)
        if risk_appetite_score >= 0.6:
            status = "risk_on"
        elif risk_appetite_score <= 0.35:
            status = "risk_off"
        else:
            status = "neutral"
        return MarketRegime(
            trade_date=trade_date,
            status=status,
            trend_score=trend_score,
            volume_score=volume_score,
            industry_score=0.5,
            risk_appetite_score=risk_appetite_score,
            reasons=[f"趋势分 {trend_score:.2f}", f"量能分 {volume_score:.2f}", f"状态 {status}"],
        )
