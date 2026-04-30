from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, is_dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Protocol, cast

from sqlalchemy import (
    JSON,
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
from sqlalchemy.engine import Engine
from sqlalchemy.sql import func

from ashare_agent.domain import (
    AnnouncementItem,
    Asset,
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
    Signal,
    SignalAction,
    SourceSnapshot,
    TechnicalIndicator,
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

    def load_latest_risk_decisions(self, trade_date: date) -> list[RiskDecision]: ...

    def load_open_positions(self) -> list[PaperPosition]: ...

    def load_paper_orders(self, trade_date: date | None = None) -> list[PaperOrder]: ...

    def load_latest_cash(self, default_cash: Decimal) -> Decimal: ...

    def load_latest_portfolio_snapshot(self) -> PortfolioSnapshot | None: ...


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
            row_payload,
        )

    def save_llm_analysis(self, context: PipelineRunContext, analysis: LLMAnalysis) -> None:
        self._save_payload("llm_analyses", context.run_id, context.trade_date, None, analysis)

    def save_universe_assets(self, context: PipelineRunContext, assets: list[Asset]) -> None:
        for asset in assets:
            self._save_payload(
                "universe_assets",
                context.run_id,
                context.trade_date,
                asset.symbol,
                asset,
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
                snapshot,
            )

    def save_market_bars(self, context: PipelineRunContext, bars: list[MarketBar]) -> None:
        for bar in bars:
            self._save_payload(
                "market_bars",
                context.run_id,
                bar.trade_date,
                bar.symbol,
                bar,
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
                announcement,
            )

    def save_news_items(self, context: PipelineRunContext, news_items: list[NewsItem]) -> None:
        for item in news_items:
            self._save_payload(
                "news_items",
                context.run_id,
                item.trade_date,
                item.symbol,
                item,
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
                item,
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
                indicator,
            )

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
                candidate,
            )

    def save_signals(self, context: PipelineRunContext, signals: list[Signal]) -> None:
        for signal in signals:
            self._save_payload(
                "signals",
                context.run_id,
                signal.trade_date,
                signal.symbol,
                signal,
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
                decision,
            )

    def save_paper_orders(self, context: PipelineRunContext, orders: list[PaperOrder]) -> None:
        for order in orders:
            self._save_payload(
                "paper_orders",
                context.run_id,
                order.trade_date,
                order.symbol,
                order,
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
                position,
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
            snapshot,
        )

    def save_review_report(self, context: PipelineRunContext, report: ReviewReport) -> None:
        self._save_payload("review_reports", context.run_id, report.trade_date, None, report)

    def load_latest_risk_decisions(self, trade_date: date) -> list[RiskDecision]:
        run_id = self._latest_successful_run_id(trade_date=trade_date, stage="pre_market")
        if run_id is None:
            return []
        return [
            _risk_decision_from_payload(cast(Mapping[str, object], row["payload"]))
            for row in self._rows("risk_decisions", trade_date=trade_date, run_id=run_id)
        ]

    def load_open_positions(self) -> list[PaperPosition]:
        latest_by_symbol: dict[str, Mapping[str, object]] = {}
        for row in self._rows("paper_positions"):
            payload = cast(Mapping[str, object], row["payload"])
            symbol = str(row.get("symbol") or payload.get("symbol", ""))
            if symbol:
                latest_by_symbol[symbol] = payload
        return [
            _paper_position_from_payload(payload)
            for payload in latest_by_symbol.values()
            if payload.get("status") == "open"
        ]

    def load_paper_orders(self, trade_date: date | None = None) -> list[PaperOrder]:
        return [
            _paper_order_from_payload(cast(Mapping[str, object], row["payload"]))
            for row in self._rows("paper_orders", trade_date=trade_date)
        ]

    def load_latest_cash(self, default_cash: Decimal) -> Decimal:
        rows = self._rows("portfolio_snapshots")
        if not rows:
            return default_cash
        payload = cast(Mapping[str, object], rows[-1]["payload"])
        return _decimal_value(payload.get("cash", default_cash))

    def load_latest_portfolio_snapshot(self) -> PortfolioSnapshot | None:
        rows = self._rows("portfolio_snapshots")
        if not rows:
            return None
        return _portfolio_snapshot_from_payload(cast(Mapping[str, object], rows[-1]["payload"]))

    def _latest_successful_run_id(self, trade_date: date, stage: str) -> str | None:
        latest_run_id: str | None = None
        for row in self._rows("pipeline_runs", trade_date=trade_date):
            payload = cast(Mapping[str, object], row["payload"])
            if payload.get("stage") == stage and payload.get("status") == "success":
                latest_run_id = str(row["run_id"])
        return latest_run_id


class InMemoryRepository(RepositoryBase):
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self._tables: dict[str, list[PayloadRecord]] = {name: [] for name in PAYLOAD_TABLES}
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
