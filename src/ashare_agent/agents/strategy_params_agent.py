from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from yaml import safe_load  # type: ignore[import-untyped]


@dataclass(frozen=True)
class SignalWeights:
    technical: float
    market: float
    event: float
    risk_penalty: float

    def snapshot(self) -> dict[str, float]:
        return {
            "technical": self.technical,
            "market": self.market,
            "event": self.event,
            "risk_penalty": self.risk_penalty,
        }


@dataclass(frozen=True)
class SignalParams:
    min_score: float
    max_daily_signals: int
    weights: SignalWeights

    def snapshot(self) -> dict[str, Any]:
        return {
            "min_score": self.min_score,
            "max_daily_signals": self.max_daily_signals,
            "weights": self.weights.snapshot(),
        }


@dataclass(frozen=True)
class RiskParams:
    max_positions: int
    target_position_pct: Decimal
    min_cash: Decimal
    max_daily_loss_pct: Decimal
    stop_loss_pct: Decimal
    price_limit_pct: Decimal
    min_holding_trade_days: int
    max_holding_trade_days: int
    blacklist: set[str]

    def snapshot(self) -> dict[str, Any]:
        return {
            "max_positions": self.max_positions,
            "target_position_pct": str(self.target_position_pct),
            "min_cash": str(self.min_cash),
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "stop_loss_pct": str(self.stop_loss_pct),
            "price_limit_pct": str(self.price_limit_pct),
            "min_holding_trade_days": self.min_holding_trade_days,
            "max_holding_trade_days": self.max_holding_trade_days,
            "blacklist": sorted(self.blacklist),
        }


@dataclass(frozen=True)
class PaperTraderParams:
    initial_cash: Decimal
    position_size_pct: Decimal
    slippage_pct: Decimal

    def snapshot(self) -> dict[str, str]:
        return {
            "initial_cash": str(self.initial_cash),
            "position_size_pct": str(self.position_size_pct),
            "slippage_pct": str(self.slippage_pct),
        }


@dataclass(frozen=True)
class StrategyParams:
    version: str
    risk: RiskParams
    paper_trader: PaperTraderParams
    signal: SignalParams

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "risk": self.risk.snapshot(),
            "paper_trader": self.paper_trader.snapshot(),
            "signal": self.signal.snapshot(),
        }


class StrategyParamsAgent:
    def __init__(self, config_path: Path) -> None:
        self.config_path = config_path

    def load(self) -> StrategyParams:
        if not self.config_path.exists():
            raise FileNotFoundError(f"策略参数配置不存在: {self.config_path}")
        raw_data = cast(object, safe_load(self.config_path.read_text(encoding="utf-8")))
        if not isinstance(raw_data, dict):
            raise ValueError("策略参数配置必须是 YAML object")
        return load_strategy_params_from_mapping(cast(dict[str, object], raw_data))


def load_strategy_params_from_mapping(raw: Mapping[str, object]) -> StrategyParams:
    version = _required_str(raw, "version")
    risk = _required_mapping(raw, "risk")
    paper_trader = _required_mapping(raw, "paper_trader")
    signal = _required_mapping(raw, "signal")
    signal_weights = _required_mapping(signal, "signal.weights")

    min_holding_trade_days = _required_int(risk, "risk.min_holding_trade_days", minimum=0)
    max_holding_trade_days = _required_int(risk, "risk.max_holding_trade_days", minimum=0)
    if max_holding_trade_days < min_holding_trade_days:
        raise ValueError(
            "策略参数配置非法: risk.max_holding_trade_days "
            "不能小于 risk.min_holding_trade_days"
        )

    return StrategyParams(
        version=version,
        risk=RiskParams(
            max_positions=_required_int(risk, "risk.max_positions", minimum=1),
            target_position_pct=_required_pct(risk, "risk.target_position_pct"),
            min_cash=_required_decimal(risk, "risk.min_cash", minimum=Decimal("0")),
            max_daily_loss_pct=_required_pct(risk, "risk.max_daily_loss_pct"),
            stop_loss_pct=_required_pct(risk, "risk.stop_loss_pct"),
            price_limit_pct=_required_pct(risk, "risk.price_limit_pct"),
            min_holding_trade_days=min_holding_trade_days,
            max_holding_trade_days=max_holding_trade_days,
            blacklist=_required_str_set(risk, "risk.blacklist"),
        ),
        paper_trader=PaperTraderParams(
            initial_cash=_required_decimal(
                paper_trader,
                "paper_trader.initial_cash",
                minimum=Decimal("0"),
            ),
            position_size_pct=_required_pct(paper_trader, "paper_trader.position_size_pct"),
            slippage_pct=_required_pct(paper_trader, "paper_trader.slippage_pct"),
        ),
        signal=SignalParams(
            min_score=_required_ratio(signal, "signal.min_score"),
            max_daily_signals=_required_int(
                signal,
                "signal.max_daily_signals",
                minimum=1,
            ),
            weights=SignalWeights(
                technical=_required_ratio(signal_weights, "signal.weights.technical"),
                market=_required_ratio(signal_weights, "signal.weights.market"),
                event=_required_ratio(signal_weights, "signal.weights.event"),
                risk_penalty=_required_ratio(signal_weights, "signal.weights.risk_penalty"),
            ),
        ),
    )


def _required(raw: Mapping[str, object], field_name: str) -> object:
    key = field_name.split(".")[-1]
    if key not in raw or raw[key] is None:
        raise ValueError(f"策略参数配置缺少 {field_name}")
    return raw[key]


def _required_mapping(raw: Mapping[str, object], field_name: str) -> Mapping[str, object]:
    value = _required(raw, field_name)
    if not isinstance(value, dict):
        raise ValueError(f"策略参数配置字段 {field_name} 必须是 object")
    return cast(Mapping[str, object], value)


def _required_str(raw: Mapping[str, object], field_name: str) -> str:
    value = str(_required(raw, field_name)).strip()
    if not value:
        raise ValueError(f"策略参数配置字段 {field_name} 不能为空")
    return value


def _required_decimal(
    raw: Mapping[str, object],
    field_name: str,
    *,
    minimum: Decimal | None = None,
) -> Decimal:
    value = _required(raw, field_name)
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"策略参数配置字段 {field_name} 必须是数字") from exc
    if minimum is not None and decimal_value < minimum:
        raise ValueError(f"策略参数配置字段 {field_name} 不能小于 {minimum}")
    return decimal_value


def _required_pct(raw: Mapping[str, object], field_name: str) -> Decimal:
    value = _required_decimal(raw, field_name, minimum=Decimal("0"))
    if value > Decimal("1"):
        raise ValueError(f"策略参数配置字段 {field_name} 必须在 0 到 1 之间")
    return value


def _required_ratio(raw: Mapping[str, object], field_name: str) -> float:
    return float(_required_pct(raw, field_name))


def _required_int(raw: Mapping[str, object], field_name: str, *, minimum: int) -> int:
    value = _required(raw, field_name)
    try:
        int_value = int(str(value))
    except ValueError as exc:
        raise ValueError(f"策略参数配置字段 {field_name} 必须是整数") from exc
    if int_value < minimum:
        raise ValueError(f"策略参数配置字段 {field_name} 不能小于 {minimum}")
    return int_value


def _required_str_set(raw: Mapping[str, object], field_name: str) -> set[str]:
    value = _required(raw, field_name)
    if not isinstance(value, list):
        raise ValueError(f"策略参数配置字段 {field_name} 必须是列表")
    values = cast(list[object], value)
    return {str(item).strip() for item in values if str(item).strip()}
