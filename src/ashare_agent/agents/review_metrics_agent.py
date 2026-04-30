from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Protocol, cast

from ashare_agent.repository import PayloadRecord


def _empty_reason_distribution() -> dict[str, int]:
    return {}


@dataclass(frozen=True)
class ReviewMetrics:
    realized_pnl: Decimal
    win_rate: float
    average_holding_days: float
    sell_reason_distribution: dict[str, int] = field(default_factory=_empty_reason_distribution)
    max_drawdown: float = 0.0


@dataclass(frozen=True)
class _ClosedTrade:
    symbol: str
    opened_at: date
    closed_at: date
    quantity: int
    entry_price: Decimal
    exit_price: Decimal

    @property
    def pnl(self) -> Decimal:
        return (self.exit_price - self.entry_price) * Decimal(self.quantity)

    @property
    def holding_days(self) -> int:
        return max((self.closed_at - self.opened_at).days, 0)

    @property
    def identity(self) -> tuple[str, date, date, int, Decimal, Decimal]:
        return (
            self.symbol,
            self.opened_at,
            self.closed_at,
            self.quantity,
            self.entry_price,
            self.exit_price,
        )


class ReviewMetricsRepository(Protocol):
    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]: ...


class ReviewMetricsAgent:
    def __init__(self, repository: ReviewMetricsRepository) -> None:
        self.repository = repository

    def metrics_as_of(self, trade_date: date) -> ReviewMetrics:
        closed_trades = self._closed_trades_as_of(trade_date)
        realized_pnl = sum((trade.pnl for trade in closed_trades), Decimal("0"))
        wins = len([trade for trade in closed_trades if trade.pnl > 0])
        win_rate = 0 if not closed_trades else wins / len(closed_trades)
        average_holding_days = (
            0
            if not closed_trades
            else sum(trade.holding_days for trade in closed_trades) / len(closed_trades)
        )
        return ReviewMetrics(
            realized_pnl=realized_pnl,
            win_rate=win_rate,
            average_holding_days=average_holding_days,
            sell_reason_distribution=self._sell_reason_distribution_as_of(trade_date),
            max_drawdown=self._max_drawdown_as_of(trade_date),
        )

    def _closed_trades_as_of(self, trade_date: date) -> list[_ClosedTrade]:
        trades: list[_ClosedTrade] = []
        seen: set[tuple[str, date, date, int, Decimal, Decimal]] = set()
        for row in self.repository.payload_rows("paper_positions"):
            if _row_date(row, "paper_positions") > trade_date:
                continue
            payload = _payload(row, "paper_positions")
            status = _required_str(payload, "paper_positions", "status")
            if status not in {"open", "closed"}:
                raise ValueError(f"paper_positions 字段 status 未知: {status}")
            if status != "closed":
                continue
            closed_at = _required_date(payload, "paper_positions", "closed_at")
            if closed_at > trade_date:
                continue
            trade = _ClosedTrade(
                symbol=_required_str(payload, "paper_positions", "symbol"),
                opened_at=_required_date(payload, "paper_positions", "opened_at"),
                closed_at=closed_at,
                quantity=_required_int(payload, "paper_positions", "quantity"),
                entry_price=_required_decimal(payload, "paper_positions", "entry_price"),
                exit_price=_required_decimal(payload, "paper_positions", "exit_price"),
            )
            if trade.identity in seen:
                continue
            seen.add(trade.identity)
            trades.append(trade)
        return trades

    def _sell_reason_distribution_as_of(self, trade_date: date) -> dict[str, int]:
        counter: Counter[str] = Counter()
        seen_order_ids: set[str] = set()
        for row in self.repository.payload_rows("paper_orders"):
            if _row_date(row, "paper_orders") > trade_date:
                continue
            payload = _payload(row, "paper_orders")
            is_real_trade = _required_bool(payload, "paper_orders", "is_real_trade")
            if is_real_trade:
                raise ValueError("复盘指标检测到真实交易订单，违反 v1 安全边界")
            side = _required_str(payload, "paper_orders", "side")
            if side not in {"buy", "sell"}:
                raise ValueError(f"paper_orders 字段 side 未知: {side}")
            order_id = _required_str(payload, "paper_orders", "order_id")
            if side != "sell" or order_id in seen_order_ids:
                continue
            seen_order_ids.add(order_id)
            counter[_required_str(payload, "paper_orders", "reason")] += 1
        return dict(counter)

    def _max_drawdown_as_of(self, trade_date: date) -> float:
        values: list[Decimal] = []
        rows = sorted(
            self.repository.payload_rows("portfolio_snapshots"),
            key=lambda row: _row_id(row, "portfolio_snapshots"),
        )
        for row in rows:
            if _row_date(row, "portfolio_snapshots") > trade_date:
                continue
            payload = _payload(row, "portfolio_snapshots")
            values.append(_required_decimal(payload, "portfolio_snapshots", "total_value"))
        if len(values) < 2:
            return 0

        peak = values[0]
        max_drawdown = Decimal("0")
        for value in values:
            if value > peak:
                peak = value
            if peak <= 0:
                continue
            drawdown = (peak - value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return float(max_drawdown)


def _payload(row: PayloadRecord, table_name: str) -> Mapping[str, object]:
    raw = row.get("payload")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{table_name} payload 必须是 JSON object")
    return cast(Mapping[str, object], raw)


def _row_id(row: PayloadRecord, table_name: str) -> int:
    return _int_value(_required_row(row, table_name, "id"), table_name, "id")


def _row_date(row: PayloadRecord, table_name: str) -> date:
    return _date_value(_required_row(row, table_name, "trade_date"), table_name, "trade_date")


def _required_row(row: PayloadRecord, table_name: str, field_name: str) -> object:
    if field_name not in row or row[field_name] is None:
        raise ValueError(f"{table_name} 缺少字段 {field_name}")
    return row[field_name]


def _required(payload: Mapping[str, object], table_name: str, field_name: str) -> object:
    if field_name not in payload or payload[field_name] is None:
        raise ValueError(f"{table_name} 缺少字段 {field_name}")
    return payload[field_name]


def _required_bool(payload: Mapping[str, object], table_name: str, field_name: str) -> bool:
    value = _required(payload, table_name, field_name)
    if not isinstance(value, bool):
        raise ValueError(f"{table_name} 字段 {field_name} 必须是 bool")
    return value


def _required_str(payload: Mapping[str, object], table_name: str, field_name: str) -> str:
    return str(_required(payload, table_name, field_name))


def _required_int(payload: Mapping[str, object], table_name: str, field_name: str) -> int:
    return _int_value(_required(payload, table_name, field_name), table_name, field_name)


def _required_date(payload: Mapping[str, object], table_name: str, field_name: str) -> date:
    return _date_value(_required(payload, table_name, field_name), table_name, field_name)


def _required_decimal(payload: Mapping[str, object], table_name: str, field_name: str) -> Decimal:
    return _decimal_value(_required(payload, table_name, field_name), table_name, field_name)


def _date_value(value: object, table_name: str, field_name: str) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效日期") from exc


def _decimal_value(value: object, table_name: str, field_name: str) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效数字") from exc


def _int_value(value: object, table_name: str, field_name: str) -> int:
    try:
        return int(str(value))
    except ValueError as exc:
        raise ValueError(f"{table_name} 字段 {field_name} 不是有效整数") from exc
