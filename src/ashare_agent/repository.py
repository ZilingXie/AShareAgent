from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol, cast

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    insert,
    select,
)
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func

from ashare_agent.domain import (
    AnnouncementItem,
    Asset,
    DataQualityReport,
    DataReliabilityReport,
    LLMAnalysis,
    MarketBar,
    NewsItem,
    OrderSide,
    PaperOrder,
    PaperPosition,
    PipelineRunContext,
    PolicyItem,
    PortfolioSnapshot,
    PositionStatus,
    ReviewReport,
    RiskDecision,
    RunMode,
    Signal,
    SignalAction,
    SourceSnapshot,
    TechnicalIndicator,
    TradingCalendarDay,
    WatchlistCandidate,
)

PAYLOAD_TABLES = (
    "pipeline_runs",
    "universe_assets",
    "raw_source_snapshots",
    "market_bars",
    "announcements",
    "news_items",
    "policy_items",
    "industry_snapshots",
    "technical_indicators",
    "data_quality_reports",
    "data_reliability_reports",
    "llm_analyses",
    "watchlist_candidates",
    "signals",
    "risk_decisions",
    "paper_orders",
    "paper_positions",
    "portfolio_snapshots",
    "review_reports",
)

PayloadRecord = dict[str, Any]


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {str(key): _jsonable(item) for key, item in mapping.items()}
    if isinstance(value, list):
        values = cast(list[object], value)
        return [_jsonable(item) for item in values]
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def _payload_dict(payload: object) -> dict[str, Any]:
    value = _jsonable(payload)
    if not isinstance(value, dict):
        raise TypeError("payload 必须能序列化为 JSON object")
    return cast(dict[str, Any], value)


def _payload_with_scope(context: PipelineRunContext, payload: object) -> dict[str, Any]:
    row_payload = _payload_dict(payload)
    row_payload["run_mode"] = context.run_mode
    row_payload["backtest_id"] = context.backtest_id
    return row_payload


def _scope_matches(
    payload: Mapping[str, object],
    *,
    run_mode: RunMode,
    backtest_id: str | None,
) -> bool:
    payload_run_mode = str(payload.get("run_mode", "normal"))
    payload_backtest_id = payload.get("backtest_id")
    if payload_run_mode != run_mode:
        return False
    if run_mode == "backtest":
        return str(payload_backtest_id) == str(backtest_id)
    return payload_backtest_id is None or str(payload_backtest_id) == ""


def _date_value(value: object) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _decimal_value(value: object) -> Decimal:
    return Decimal(str(value))


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [str(item) for item in values]


def _signal_action(value: object) -> SignalAction:
    text = str(value)
    if text not in {"observe", "paper_buy", "paper_sell"}:
        raise ValueError(f"未知 signal_action: {text}")
    return cast(SignalAction, text)


def _position_status(value: object) -> PositionStatus:
    text = str(value)
    if text not in {"open", "closed"}:
        raise ValueError(f"未知 position status: {text}")
    return cast(PositionStatus, text)


def _optional_date(value: object) -> date | None:
    if value is None:
        return None
    return _date_value(value)


def _optional_datetime(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _optional_decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    return _decimal_value(value)


def _risk_decision_from_payload(payload: Mapping[str, object]) -> RiskDecision:
    return RiskDecision(
        symbol=str(payload["symbol"]),
        trade_date=_date_value(payload["trade_date"]),
        signal_action=_signal_action(payload["signal_action"]),
        approved=bool(payload["approved"]),
        reasons=_string_list(payload.get("reasons", [])),
        target_position_pct=_decimal_value(payload.get("target_position_pct", "0")),
    )


def _paper_position_from_payload(payload: Mapping[str, object]) -> PaperPosition:
    return PaperPosition(
        symbol=str(payload["symbol"]),
        opened_at=_date_value(payload["opened_at"]),
        quantity=int(str(payload["quantity"])),
        entry_price=_decimal_value(payload["entry_price"]),
        current_price=_decimal_value(payload["current_price"]),
        status=_position_status(payload["status"]),
        closed_at=_optional_date(payload.get("closed_at")),
        exit_price=_optional_decimal(payload.get("exit_price")),
    )


def _paper_order_from_payload(payload: Mapping[str, object]) -> PaperOrder:
    return PaperOrder(
        order_id=str(payload["order_id"]),
        symbol=str(payload["symbol"]),
        trade_date=_date_value(payload["trade_date"]),
        side=cast(OrderSide, payload["side"]),
        quantity=int(str(payload["quantity"])),
        price=_decimal_value(payload["price"]),
        amount=_decimal_value(payload["amount"]),
        slippage=_decimal_value(payload["slippage"]),
        reason=str(payload["reason"]),
        is_real_trade=bool(payload.get("is_real_trade", False)),
        execution_source=(
            str(payload["execution_source"])
            if payload.get("execution_source") is not None
            else None
        ),
        execution_timestamp=_optional_datetime(payload.get("execution_timestamp")),
        execution_method=(
            str(payload["execution_method"])
            if payload.get("execution_method") is not None
            else None
        ),
        reference_price=_optional_decimal(payload.get("reference_price")),
        used_daily_fallback=bool(payload.get("used_daily_fallback", False)),
        execution_failure_reason=(
            str(payload["execution_failure_reason"])
            if payload.get("execution_failure_reason") is not None
            else None
        ),
    )


def _portfolio_snapshot_from_payload(payload: Mapping[str, object]) -> PortfolioSnapshot:
    return PortfolioSnapshot(
        trade_date=_date_value(payload["trade_date"]),
        cash=_decimal_value(payload["cash"]),
        market_value=_decimal_value(payload["market_value"]),
        total_value=_decimal_value(payload["total_value"]),
        open_positions=int(str(payload["open_positions"])),
    )


class PipelineRepository(Protocol):
    def save_artifact(self, trade_date: date, artifact_type: str, payload: dict[str, Any]) -> None:
        ...

    def save_pipeline_run(
        self,
        context: PipelineRunContext,
        stage: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        ...

    def save_llm_analysis(self, context: PipelineRunContext, analysis: LLMAnalysis) -> None: ...

    def save_universe_assets(self, context: PipelineRunContext, assets: list[Asset]) -> None: ...

    def save_raw_source_snapshots(
        self,
        context: PipelineRunContext,
        snapshots: list[SourceSnapshot],
    ) -> None:
        ...

    def save_market_bars(self, context: PipelineRunContext, bars: list[MarketBar]) -> None: ...

    def save_announcements(
        self,
        context: PipelineRunContext,
        announcements: list[AnnouncementItem],
    ) -> None:
        ...

    def save_news_items(self, context: PipelineRunContext, news_items: list[NewsItem]) -> None:
        ...

    def save_policy_items(
        self,
        context: PipelineRunContext,
        policy_items: list[PolicyItem],
    ) -> None:
        ...

    def save_technical_indicators(
        self,
        context: PipelineRunContext,
        indicators: list[TechnicalIndicator],
    ) -> None:
        ...

    def save_data_quality_report(
        self,
        context: PipelineRunContext,
        report: DataQualityReport,
    ) -> None:
        ...

    def save_data_reliability_report(
        self,
        context: PipelineRunContext,
        report: DataReliabilityReport,
    ) -> None:
        ...

    def save_trading_calendar_days(
        self,
        context: PipelineRunContext,
        days: list[TradingCalendarDay],
    ) -> None:
        ...

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]:
        ...

    def save_watchlist_candidates(
        self,
        context: PipelineRunContext,
        candidates: list[WatchlistCandidate],
    ) -> None:
        ...

    def save_signals(self, context: PipelineRunContext, signals: list[Signal]) -> None: ...

    def save_risk_decisions(
        self,
        context: PipelineRunContext,
        decisions: list[RiskDecision],
    ) -> None:
        ...

    def save_paper_orders(self, context: PipelineRunContext, orders: list[PaperOrder]) -> None:
        ...

    def save_paper_positions(
        self,
        context: PipelineRunContext,
        positions: list[PaperPosition],
    ) -> None:
        ...

    def save_portfolio_snapshot(
        self,
        context: PipelineRunContext,
        snapshot: PortfolioSnapshot,
    ) -> None:
        ...

    def save_review_report(self, context: PipelineRunContext, report: ReviewReport) -> None: ...

    def load_latest_risk_decisions(
        self,
        trade_date: date,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> list[RiskDecision]: ...

    def load_open_positions(
        self,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> list[PaperPosition]: ...

    def load_paper_orders(
        self,
        trade_date: date | None = None,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
        stage: str | None = None,
    ) -> list[PaperOrder]: ...

    def load_latest_cash(
        self,
        default_cash: Decimal,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> Decimal: ...

    def load_latest_portfolio_snapshot(
        self,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> PortfolioSnapshot | None: ...

    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]: ...

    def payload_rows_for_backtest(
        self,
        table_name: str,
        backtest_id: str,
    ) -> list[PayloadRecord]: ...


class RepositoryBase:
    def _save_payload(
        self,
        table_name: str,
        run_id: str,
        trade_date: date,
        symbol: str | None,
        payload: object,
    ) -> None:
        raise NotImplementedError

    def _rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]:
        raise NotImplementedError

    def _rows_for_backtest(self, table_name: str, backtest_id: str) -> list[PayloadRecord]:
        return [
            row
            for row in self._rows(table_name)
            if _scope_matches(
                cast(Mapping[str, object], row["payload"]),
                run_mode="backtest",
                backtest_id=backtest_id,
            )
        ]

    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]:
        if table_name not in PAYLOAD_TABLES:
            raise ValueError(f"未知 payload table: {table_name}")
        return self._rows(table_name, trade_date=trade_date, run_id=run_id)

    def payload_rows_for_backtest(
        self,
        table_name: str,
        backtest_id: str,
    ) -> list[PayloadRecord]:
        if table_name not in PAYLOAD_TABLES:
            raise ValueError(f"未知 payload table: {table_name}")
        return self._rows_for_backtest(table_name, backtest_id=backtest_id)

    def save_pipeline_run(
        self,
        context: PipelineRunContext,
        stage: str,
        status: str,
        payload: dict[str, Any],
    ) -> None:
        row_payload = {
            "stage": stage,
            "status": status,
            "run_id": context.run_id,
            "created_at": context.created_at,
            **payload,
        }
        self._save_payload(
            "pipeline_runs",
            context.run_id,
            context.trade_date,
            None,
            _payload_with_scope(context, row_payload),
        )

    def save_llm_analysis(self, context: PipelineRunContext, analysis: LLMAnalysis) -> None:
        self._save_payload(
            "llm_analyses",
            context.run_id,
            context.trade_date,
            None,
            _payload_with_scope(context, analysis),
        )

    def save_universe_assets(self, context: PipelineRunContext, assets: list[Asset]) -> None:
        for asset in assets:
            self._save_payload(
                "universe_assets",
                context.run_id,
                context.trade_date,
                asset.symbol,
                _payload_with_scope(context, asset),
            )

    def save_raw_source_snapshots(
        self,
        context: PipelineRunContext,
        snapshots: list[SourceSnapshot],
    ) -> None:
        for snapshot in snapshots:
            self._save_payload(
                "raw_source_snapshots",
                context.run_id,
                snapshot.trade_date,
                None,
                _payload_with_scope(context, snapshot),
            )

    def save_market_bars(self, context: PipelineRunContext, bars: list[MarketBar]) -> None:
        for bar in bars:
            self._save_payload(
                "market_bars",
                context.run_id,
                bar.trade_date,
                bar.symbol,
                _payload_with_scope(context, bar),
            )

    def save_announcements(
        self,
        context: PipelineRunContext,
        announcements: list[AnnouncementItem],
    ) -> None:
        for announcement in announcements:
            self._save_payload(
                "announcements",
                context.run_id,
                announcement.trade_date,
                announcement.symbol,
                _payload_with_scope(context, announcement),
            )

    def save_news_items(self, context: PipelineRunContext, news_items: list[NewsItem]) -> None:
        for item in news_items:
            self._save_payload(
                "news_items",
                context.run_id,
                item.trade_date,
                item.symbol,
                _payload_with_scope(context, item),
            )

    def save_policy_items(
        self,
        context: PipelineRunContext,
        policy_items: list[PolicyItem],
    ) -> None:
        for item in policy_items:
            self._save_payload(
                "policy_items",
                context.run_id,
                item.trade_date,
                None,
                _payload_with_scope(context, item),
            )

    def save_technical_indicators(
        self,
        context: PipelineRunContext,
        indicators: list[TechnicalIndicator],
    ) -> None:
        for indicator in indicators:
            self._save_payload(
                "technical_indicators",
                context.run_id,
                indicator.trade_date,
                indicator.symbol,
                _payload_with_scope(context, indicator),
            )

    def save_data_quality_report(
        self,
        context: PipelineRunContext,
        report: DataQualityReport,
    ) -> None:
        self._save_payload(
            "data_quality_reports",
            context.run_id,
            report.trade_date,
            None,
            _payload_with_scope(context, report),
        )

    def save_data_reliability_report(
        self,
        context: PipelineRunContext,
        report: DataReliabilityReport,
    ) -> None:
        self._save_payload(
            "data_reliability_reports",
            context.run_id,
            report.trade_date,
            None,
            _payload_with_scope(context, report),
        )

    def save_trading_calendar_days(
        self,
        context: PipelineRunContext,
        days: list[TradingCalendarDay],
    ) -> None:
        raise NotImplementedError

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]:
        raise NotImplementedError

    def save_watchlist_candidates(
        self,
        context: PipelineRunContext,
        candidates: list[WatchlistCandidate],
    ) -> None:
        for candidate in candidates:
            self._save_payload(
                "watchlist_candidates",
                context.run_id,
                candidate.trade_date,
                candidate.symbol,
                _payload_with_scope(context, candidate),
            )

    def save_signals(self, context: PipelineRunContext, signals: list[Signal]) -> None:
        for signal in signals:
            self._save_payload(
                "signals",
                context.run_id,
                signal.trade_date,
                signal.symbol,
                _payload_with_scope(context, signal),
            )

    def save_risk_decisions(
        self,
        context: PipelineRunContext,
        decisions: list[RiskDecision],
    ) -> None:
        for decision in decisions:
            self._save_payload(
                "risk_decisions",
                context.run_id,
                decision.trade_date,
                decision.symbol,
                _payload_with_scope(context, decision),
            )

    def save_paper_orders(self, context: PipelineRunContext, orders: list[PaperOrder]) -> None:
        for order in orders:
            self._save_payload(
                "paper_orders",
                context.run_id,
                order.trade_date,
                order.symbol,
                _payload_with_scope(context, order),
            )

    def save_paper_positions(
        self,
        context: PipelineRunContext,
        positions: list[PaperPosition],
    ) -> None:
        for position in positions:
            self._save_payload(
                "paper_positions",
                context.run_id,
                context.trade_date,
                position.symbol,
                _payload_with_scope(context, position),
            )

    def save_portfolio_snapshot(
        self,
        context: PipelineRunContext,
        snapshot: PortfolioSnapshot,
    ) -> None:
        self._save_payload(
            "portfolio_snapshots",
            context.run_id,
            snapshot.trade_date,
            None,
            _payload_with_scope(context, snapshot),
        )

    def save_review_report(self, context: PipelineRunContext, report: ReviewReport) -> None:
        self._save_payload(
            "review_reports",
            context.run_id,
            report.trade_date,
            None,
            _payload_with_scope(context, report),
        )

    def load_latest_risk_decisions(
        self,
        trade_date: date,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> list[RiskDecision]:
        run_id = self._latest_successful_run_id(
            trade_date=trade_date,
            stage="pre_market",
            run_mode=run_mode,
            backtest_id=backtest_id,
        )
        if run_id is None:
            return []
        return [
            _risk_decision_from_payload(cast(Mapping[str, object], row["payload"]))
            for row in self._rows("risk_decisions", trade_date=trade_date, run_id=run_id)
            if _scope_matches(
                cast(Mapping[str, object], row["payload"]),
                run_mode=run_mode,
                backtest_id=backtest_id,
            )
        ]

    def load_open_positions(
        self,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> list[PaperPosition]:
        latest_by_symbol: dict[str, Mapping[str, object]] = {}
        for row in self._rows("paper_positions"):
            payload = cast(Mapping[str, object], row["payload"])
            if not _scope_matches(payload, run_mode=run_mode, backtest_id=backtest_id):
                continue
            symbol = str(row.get("symbol") or payload.get("symbol", ""))
            if symbol:
                latest_by_symbol[symbol] = payload
        return [
            _paper_position_from_payload(payload)
            for payload in latest_by_symbol.values()
            if payload.get("status") == "open"
        ]

    def load_paper_orders(
        self,
        trade_date: date | None = None,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
        stage: str | None = None,
    ) -> list[PaperOrder]:
        if stage is not None:
            if trade_date is None:
                raise ValueError("按 stage 读取 paper_orders 必须提供 trade_date")
            run_id = self._latest_successful_run_id(
                trade_date=trade_date,
                stage=stage,
                run_mode=run_mode,
                backtest_id=backtest_id,
            )
            if run_id is None:
                return []
            rows = self._rows("paper_orders", trade_date=trade_date, run_id=run_id)
        else:
            rows = self._rows("paper_orders", trade_date=trade_date)
        return [
            _paper_order_from_payload(cast(Mapping[str, object], row["payload"]))
            for row in rows
            if _scope_matches(
                cast(Mapping[str, object], row["payload"]),
                run_mode=run_mode,
                backtest_id=backtest_id,
            )
        ]

    def load_latest_cash(
        self,
        default_cash: Decimal,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> Decimal:
        rows = [
            row
            for row in self._rows("portfolio_snapshots")
            if _scope_matches(
                cast(Mapping[str, object], row["payload"]),
                run_mode=run_mode,
                backtest_id=backtest_id,
            )
        ]
        if not rows:
            return default_cash
        payload = cast(Mapping[str, object], rows[-1]["payload"])
        return _decimal_value(payload.get("cash", default_cash))

    def load_latest_portfolio_snapshot(
        self,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> PortfolioSnapshot | None:
        rows = [
            row
            for row in self._rows("portfolio_snapshots")
            if _scope_matches(
                cast(Mapping[str, object], row["payload"]),
                run_mode=run_mode,
                backtest_id=backtest_id,
            )
        ]
        if not rows:
            return None
        return _portfolio_snapshot_from_payload(cast(Mapping[str, object], rows[-1]["payload"]))

    def _latest_successful_run_id(
        self,
        trade_date: date,
        stage: str,
        run_mode: RunMode = "normal",
        backtest_id: str | None = None,
    ) -> str | None:
        latest_run_id: str | None = None
        for row in self._rows("pipeline_runs", trade_date=trade_date):
            payload = cast(Mapping[str, object], row["payload"])
            if not _scope_matches(payload, run_mode=run_mode, backtest_id=backtest_id):
                continue
            if payload.get("stage") == stage and payload.get("status") == "success":
                latest_run_id = str(row["run_id"])
        return latest_run_id


class InMemoryRepository(RepositoryBase):
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._tables: dict[str, list[PayloadRecord]] = {name: [] for name in PAYLOAD_TABLES}
        self._trading_calendar: dict[tuple[date, str], TradingCalendarDay] = {}
        self._next_id = 1

    def save_artifact(self, trade_date: date, artifact_type: str, payload: dict[str, Any]) -> None:
        self.records.append(
            {
                "trade_date": trade_date,
                "artifact_type": artifact_type,
                "payload": _jsonable(payload),
            }
        )

    def records_for(self, table_name: str) -> list[PayloadRecord]:
        return list(self._tables.get(table_name, []))

    def _save_payload(
        self,
        table_name: str,
        run_id: str,
        trade_date: date,
        symbol: str | None,
        payload: object,
    ) -> None:
        self._tables.setdefault(table_name, []).append(
            {
                "id": self._next_id,
                "run_id": run_id,
                "trade_date": trade_date,
                "symbol": symbol,
                "payload": _payload_dict(payload),
            }
        )
        self._next_id += 1

    def _rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]:
        rows = self._tables.get(table_name, [])
        return [
            row
            for row in rows
            if (trade_date is None or row["trade_date"] == trade_date)
            and (run_id is None or row["run_id"] == run_id)
        ]

    def save_trading_calendar_days(
        self,
        context: PipelineRunContext,
        days: list[TradingCalendarDay],
    ) -> None:
        for day in days:
            self._trading_calendar[(day.calendar_date, day.source)] = day

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]:
        rows = sorted(
            self._trading_calendar.values(),
            key=lambda item: (item.calendar_date, item.source),
        )
        return [
            row
            for row in rows
            if (start_date is None or row.calendar_date >= start_date)
            and (end_date is None or row.calendar_date <= end_date)
        ]


class PostgresRepository(RepositoryBase):
    def __init__(self, database_url: str) -> None:
        self.engine = create_engine(database_url)
        self.metadata = MetaData(schema="ashare_agent")
        self._tables = {
            table_name: Table(
                table_name,
                self.metadata,
                autoload_with=self.engine,
            )
            for table_name in PAYLOAD_TABLES
        }
        self.artifacts = Table(
            "artifacts",
            self.metadata,
            # Schema is created by Alembic; repository does not auto-migrate.
            autoload_with=self.engine,
        )
        self.trading_calendar = Table(
            "trading_calendar",
            self.metadata,
            autoload_with=self.engine,
        )

    @classmethod
    def from_engine(cls, engine: Engine) -> PostgresRepository:
        instance = cls.__new__(cls)
        instance.engine = engine
        instance.metadata = MetaData(schema="ashare_agent")
        instance._tables = {
            table_name: Table(
                table_name,
                instance.metadata,
                autoload_with=engine,
            )
            for table_name in PAYLOAD_TABLES
        }
        instance.artifacts = Table(
            "artifacts",
            instance.metadata,
            autoload_with=engine,
        )
        instance.trading_calendar = Table(
            "trading_calendar",
            instance.metadata,
            autoload_with=engine,
        )
        return instance

    def save_artifact(self, trade_date: date, artifact_type: str, payload: dict[str, Any]) -> None:
        with self.engine.begin() as conn:
            conn.execute(
                insert(self.artifacts).values(
                    trade_date=trade_date,
                    artifact_type=artifact_type,
                    payload=_jsonable(payload),
                )
            )

    def _save_payload(
        self,
        table_name: str,
        run_id: str,
        trade_date: date,
        symbol: str | None,
        payload: object,
    ) -> None:
        table = self._tables[table_name]
        with self.engine.begin() as conn:
            conn.execute(
                insert(table).values(
                    run_id=run_id,
                    trade_date=trade_date,
                    symbol=symbol,
                    payload=_payload_dict(payload),
                )
            )

    def _rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]:
        table = self._tables[table_name]
        statement = select(table).order_by(table.c.id.asc())
        if trade_date is not None:
            statement = statement.where(table.c.trade_date == trade_date)
        if run_id is not None:
            statement = statement.where(table.c.run_id == run_id)
        with self.engine.begin() as conn:
            rows = conn.execute(statement).mappings().all()
        return [
            {
                "id": int(row["id"]),
                "run_id": str(row["run_id"]),
                "trade_date": row["trade_date"],
                "symbol": row["symbol"],
                "payload": cast(dict[str, Any], row["payload"]),
            }
            for row in rows
        ]

    def _rows_for_backtest(self, table_name: str, backtest_id: str) -> list[PayloadRecord]:
        table = self._tables[table_name]
        statement = (
            select(table)
            .where(table.c.payload["run_mode"].as_string() == "backtest")
            .where(table.c.payload["backtest_id"].as_string() == backtest_id)
            .order_by(table.c.id.asc())
        )
        with self.engine.begin() as conn:
            rows = conn.execute(statement).mappings().all()
        return [
            {
                "id": int(row["id"]),
                "run_id": str(row["run_id"]),
                "trade_date": row["trade_date"],
                "symbol": row["symbol"],
                "payload": cast(dict[str, Any], row["payload"]),
            }
            for row in rows
        ]

    def save_trading_calendar_days(
        self,
        context: PipelineRunContext,
        days: list[TradingCalendarDay],
    ) -> None:
        if not days:
            return
        values = [
            {
                "calendar_date": day.calendar_date,
                "is_trade_date": day.is_trade_date,
                "source": day.source,
                "collected_at": day.collected_at,
            }
            for day in days
        ]
        with self.engine.begin() as conn:
            for start in range(0, len(values), 5000):
                statement = postgresql_insert(self.trading_calendar).values(
                    values[start : start + 5000]
                )
                statement = statement.on_conflict_do_update(
                    index_elements=["calendar_date", "source"],
                    set_={
                        "is_trade_date": statement.excluded.is_trade_date,
                        "collected_at": statement.excluded.collected_at,
                    },
                )
                conn.execute(statement)

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]:
        statement = select(self.trading_calendar).order_by(
            self.trading_calendar.c.calendar_date.asc(),
            self.trading_calendar.c.source.asc(),
        )
        if start_date is not None:
            statement = statement.where(self.trading_calendar.c.calendar_date >= start_date)
        if end_date is not None:
            statement = statement.where(self.trading_calendar.c.calendar_date <= end_date)
        with self.engine.begin() as conn:
            rows = conn.execute(statement).mappings().all()
        return [
            TradingCalendarDay(
                calendar_date=row["calendar_date"],
                is_trade_date=bool(row["is_trade_date"]),
                source=str(row["source"]),
                collected_at=row["collected_at"],
            )
            for row in rows
        ]


metadata = MetaData(schema="ashare_agent")
artifacts_table = Table(
    "artifacts",
    metadata,
    # Definitions here mirror migration for metadata consumers.
    Column("id", Integer, primary_key=True),
    Column("trade_date", Date, nullable=False),
    Column("artifact_type", String(80), nullable=False),
    Column("payload", JSON, nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
    Column("failure_reason", Text),
)

trading_calendar_table = Table(
    "trading_calendar",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("calendar_date", Date, nullable=False),
    Column("is_trade_date", Boolean, nullable=False),
    Column("source", String(80), nullable=False),
    Column("collected_at", DateTime(timezone=True), nullable=False),
    Column(
        "created_at",
        DateTime(timezone=True),
        server_default=func.now(),
    ),
)
