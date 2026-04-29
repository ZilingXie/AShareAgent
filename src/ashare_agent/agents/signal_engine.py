from __future__ import annotations

from collections import defaultdict
from datetime import date

from ashare_agent.domain import (
    AnnouncementEvent,
    MarketRegime,
    Signal,
    SignalResult,
    TechnicalIndicator,
    WatchlistCandidate,
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


class SignalEngine:
    def __init__(self, min_score: float = 0.55) -> None:
        self._min_score = min_score

    def generate(
        self,
        trade_date: date,
        indicators: list[TechnicalIndicator],
        events: list[AnnouncementEvent],
        regime: MarketRegime,
    ) -> SignalResult:
        events_by_symbol: dict[str, list[AnnouncementEvent]] = defaultdict(list)
        for event in events:
            events_by_symbol[event.symbol].append(event)

        watchlist: list[WatchlistCandidate] = []
        for indicator in indicators:
            symbol_events = events_by_symbol[indicator.symbol]
            technical = self._technical_score(indicator)
            market = self._market_score(regime)
            event_score = self._event_score(symbol_events)
            risk_penalty = self._risk_penalty(symbol_events)
            weighted = {
                "technical": round(technical * 0.45, 4),
                "market": round(market * 0.25, 4),
                "event": round(event_score * 0.20, 4),
                "risk_penalty": round(risk_penalty * 0.10, 4),
            }
            score = (
                weighted["technical"]
                + weighted["market"]
                + weighted["event"]
                - weighted["risk_penalty"]
            )
            reasons = [
                f"技术面 {technical:.2f}",
                f"市场环境 {regime.status}",
                f"事件面 {event_score:.2f}",
            ]
            if risk_penalty:
                reasons.append(f"风险惩罚 {risk_penalty:.2f}")
            watchlist.append(
                WatchlistCandidate(
                    symbol=indicator.symbol,
                    trade_date=trade_date,
                    score=round(score, 4),
                    score_breakdown=weighted,
                    reasons=reasons,
                )
            )

        ranked = sorted(watchlist, key=lambda item: item.score, reverse=True)
        signals: list[Signal] = []
        if ranked and ranked[0].score >= self._min_score:
            top = ranked[0]
            signals.append(
                Signal(
                    symbol=top.symbol,
                    trade_date=trade_date,
                    action="paper_buy",
                    score=top.score,
                    score_breakdown=top.score_breakdown,
                    reasons=top.reasons,
                )
            )
        return SignalResult(watchlist=ranked, signals=signals)

    def _technical_score(self, indicator: TechnicalIndicator) -> float:
        score = 0.0
        score += 0.25 if indicator.close_above_ma5 else 0.0
        score += 0.25 if indicator.close_above_ma20 else 0.0
        score += _clamp(indicator.return_5d / 0.05) * 0.25
        score += _clamp(indicator.volume_ratio / 1.5) * 0.25
        return _clamp(score)

    def _market_score(self, regime: MarketRegime) -> float:
        if regime.status == "risk_on":
            return 0.85
        if regime.status == "neutral":
            return 0.50
        return 0.15

    def _event_score(self, events: list[AnnouncementEvent]) -> float:
        if not events:
            return 0.5
        score = 0.5
        for event in events:
            if event.sentiment == "positive":
                score += 0.25 if event.is_material else 0.15
            elif event.sentiment == "negative":
                score -= 0.30 if event.is_material else 0.15
        return _clamp(score)

    def _risk_penalty(self, events: list[AnnouncementEvent]) -> float:
        return 1.0 if any(event.exclude for event in events) else 0.0
