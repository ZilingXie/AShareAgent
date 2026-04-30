from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from ashare_agent.agents.strategy_params_agent import SignalParams, SignalWeights
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
    def __init__(
        self,
        params: SignalParams | None = None,
        *,
        strategy_params_version: str | None = None,
        strategy_params_snapshot: dict[str, Any] | None = None,
    ) -> None:
        self._params = params or SignalParams(
            min_score=0.55,
            max_daily_signals=1,
            weights=SignalWeights(
                technical=0.45,
                market=0.25,
                event=0.20,
                risk_penalty=0.10,
            ),
        )
        self._strategy_params_version = strategy_params_version
        self._strategy_params_snapshot = strategy_params_snapshot or {}

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
                "technical": round(technical * self._params.weights.technical, 4),
                "market": round(market * self._params.weights.market, 4),
                "event": round(event_score * self._params.weights.event, 4),
                "risk_penalty": round(risk_penalty * self._params.weights.risk_penalty, 4),
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
                    strategy_params_version=self._strategy_params_version,
                    strategy_params_snapshot=self._strategy_params_snapshot,
                )
            )

        ranked = sorted(watchlist, key=lambda item: item.score, reverse=True)
        signals: list[Signal] = []
        for top in [
            item for item in ranked if item.score >= self._params.min_score
        ][: self._params.max_daily_signals]:
            signals.append(
                Signal(
                    symbol=top.symbol,
                    trade_date=trade_date,
                    action="paper_buy",
                    score=top.score,
                    score_breakdown=top.score_breakdown,
                    reasons=top.reasons,
                    strategy_params_version=self._strategy_params_version,
                    strategy_params_snapshot=self._strategy_params_snapshot,
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
