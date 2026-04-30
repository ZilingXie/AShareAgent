from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import uuid4

AssetType = Literal["ETF", "STOCK"]
RegimeStatus = Literal["risk_on", "neutral", "risk_off"]
SignalAction = Literal["observe", "paper_buy", "paper_sell"]
OrderSide = Literal["buy", "sell"]
PositionStatus = Literal["open", "closed"]
ExitReason = Literal["stop_loss", "trend_weakness", "max_holding_days"]
DataQualitySeverity = Literal["warning", "error"]
DataQualityStatus = Literal["passed", "warning", "failed"]
RunMode = Literal["normal", "backtest"]


def now_utc() -> datetime:
    return datetime.now(UTC)


def empty_str_list() -> list[str]:
    return []


def empty_dict() -> dict[str, Any]:
    return {}


def empty_date_list() -> list[date]:
    return []


@dataclass(frozen=True)
class Asset:
    symbol: str
    name: str
    asset_type: AssetType
    market: str = "A_SHARE"
    enabled: bool = True


@dataclass(frozen=True)
class MarketBar:
    symbol: str
    trade_date: date
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int
    amount: Decimal
    source: str
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class AnnouncementItem:
    symbol: str
    name: str
    title: str
    category: str
    published_at: datetime
    url: str
    source: str
    trade_date: date
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class NewsItem:
    symbol: str
    title: str
    content: str
    published_at: datetime
    source: str
    url: str
    trade_date: date
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class PolicyItem:
    title: str
    content: str
    published_at: datetime
    source: str
    trade_date: date
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class IndustrySnapshot:
    industry: str
    strength_score: float
    source: str
    trade_date: date
    reasons: list[str] = field(default_factory=empty_str_list)
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class SourceSnapshot:
    source: str
    trade_date: date
    status: Literal["success", "failed"]
    collected_at: datetime = field(default_factory=now_utc)
    failure_reason: str | None = None
    row_count: int = 0
    metadata: dict[str, Any] = field(default_factory=empty_dict)


@dataclass(frozen=True)
class TradingCalendarSnapshot:
    trade_date: date
    is_trade_date: bool
    row_count: int
    source: str
    calendar_start: date | None = None
    calendar_end: date | None = None
    collected_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class MarketDataset:
    trade_date: date
    assets: list[Asset]
    bars: list[MarketBar]
    announcements: list[AnnouncementItem]
    news: list[NewsItem]
    policy_items: list[PolicyItem]
    industry_snapshots: list[IndustrySnapshot]
    source_snapshots: list[SourceSnapshot]
    trade_calendar: TradingCalendarSnapshot | None = None
    trade_calendar_dates: list[date] = field(default_factory=empty_date_list)


@dataclass(frozen=True)
class AnnouncementEvent:
    symbol: str
    trade_date: date
    category: str
    sentiment: Literal["positive", "neutral", "negative"]
    is_material: bool
    exclude: bool
    reasons: list[str]


@dataclass(frozen=True)
class TechnicalIndicator:
    symbol: str
    trade_date: date
    close_above_ma5: bool
    close_above_ma20: bool
    return_5d: float
    return_20d: float
    volume_ratio: float


@dataclass(frozen=True)
class DataQualityIssue:
    severity: DataQualitySeverity
    check_name: str
    message: str
    source: str | None = None
    symbol: str | None = None
    metadata: dict[str, Any] = field(default_factory=empty_dict)


@dataclass(frozen=True)
class DataQualityReport:
    trade_date: date
    stage: str
    status: DataQualityStatus
    source_failure_rate: float
    total_sources: int
    failed_source_count: int
    empty_source_count: int
    missing_market_bar_count: int
    abnormal_price_count: int
    is_trade_date: bool | None
    issues: list[DataQualityIssue]
    created_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class MarketRegime:
    trade_date: date
    status: RegimeStatus
    trend_score: float
    volume_score: float
    industry_score: float
    risk_appetite_score: float
    reasons: list[str]


@dataclass(frozen=True)
class LLMAnalysis:
    trade_date: date
    model: str
    summary: str
    key_points: list[str]
    risk_notes: list[str]
    raw_response: dict[str, Any]
    created_at: datetime = field(default_factory=now_utc)


@dataclass(frozen=True)
class WatchlistCandidate:
    symbol: str
    trade_date: date
    score: float
    score_breakdown: dict[str, float]
    reasons: list[str]
    strategy_params_version: str | None = None
    strategy_params_snapshot: dict[str, Any] = field(default_factory=empty_dict)


@dataclass(frozen=True)
class Signal:
    symbol: str
    trade_date: date
    action: SignalAction
    score: float
    score_breakdown: dict[str, float]
    reasons: list[str]
    strategy_params_version: str | None = None
    strategy_params_snapshot: dict[str, Any] = field(default_factory=empty_dict)


@dataclass(frozen=True)
class SignalResult:
    watchlist: list[WatchlistCandidate]
    signals: list[Signal]


@dataclass(frozen=True)
class RiskDecision:
    symbol: str
    trade_date: date
    signal_action: SignalAction
    approved: bool
    reasons: list[str]
    target_position_pct: Decimal = Decimal("0")


@dataclass(frozen=True)
class ExitDecision:
    symbol: str
    trade_date: date
    approved: bool
    reasons: list[str]
    exit_reason: ExitReason | None = None


@dataclass(frozen=True)
class PaperOrder:
    order_id: str
    symbol: str
    trade_date: date
    side: OrderSide
    quantity: int
    price: Decimal
    amount: Decimal
    slippage: Decimal
    reason: str
    is_real_trade: bool = False
    created_at: datetime = field(default_factory=now_utc)


@dataclass
class PaperPosition:
    symbol: str
    opened_at: date
    quantity: int
    entry_price: Decimal
    current_price: Decimal
    status: PositionStatus
    closed_at: date | None = None
    exit_price: Decimal | None = None

    @property
    def market_value(self) -> Decimal:
        return self.current_price * Decimal(self.quantity)


@dataclass(frozen=True)
class PaperTradeResult:
    cash: Decimal
    orders: list[PaperOrder]
    positions: list[PaperPosition]


@dataclass(frozen=True)
class PortfolioSnapshot:
    trade_date: date
    cash: Decimal
    market_value: Decimal
    total_value: Decimal
    open_positions: int


@dataclass(frozen=True)
class ReviewReport:
    trade_date: date
    summary: str
    stats: dict[str, float]
    attribution: list[str]
    parameter_suggestions: list[str]


@dataclass(frozen=True)
class PipelineRunContext:
    trade_date: date
    run_id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=now_utc)
    run_mode: RunMode = "normal"
    backtest_id: str | None = None


@dataclass(frozen=True)
class AgentResult:
    name: str
    success: bool
    payload: dict[str, Any]
    reasons: list[str] = field(default_factory=empty_str_list)
