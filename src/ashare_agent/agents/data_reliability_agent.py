from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from datetime import date
from typing import Literal, Protocol, cast

from ashare_agent.domain import (
    Asset,
    AssetType,
    DataReliabilityIssue,
    DataReliabilityReport,
    DataReliabilityStatus,
    DataSourceHealth,
    MarketBarGap,
    TradingCalendarDay,
)
from ashare_agent.repository import PayloadRecord

SourceHealthStatus = Literal["success", "failed", "empty", "mixed"]


class DataReliabilityRepository(Protocol):
    def payload_rows(
        self,
        table_name: str,
        trade_date: date | None = None,
        run_id: str | None = None,
    ) -> list[PayloadRecord]: ...

    def trading_calendar_days(
        self,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> list[TradingCalendarDay]: ...


class DataReliabilityAgent:
    def __init__(
        self,
        repository: DataReliabilityRepository,
        *,
        required_data_sources: set[str] | None = None,
        lookback_trade_days: int = 30,
    ) -> None:
        self.repository = repository
        self._required_data_sources = required_data_sources or set()
        self._lookback_trade_days = lookback_trade_days

    def analyze(self, trade_date: date) -> DataReliabilityReport:
        source_health, source_issues = self._source_health(trade_date)
        is_trade_date = self._is_trade_date(trade_date)
        issues = list(source_issues)
        market_bar_gaps: list[MarketBarGap] = []
        missing_market_bar_count = 0

        if is_trade_date is False:
            issues.append(
                DataReliabilityIssue(
                    severity="warning",
                    check_name="non_trade_date",
                    source="trade_calendar",
                    message=f"{trade_date.isoformat()} 不是交易日，跳过行情缺口检查",
                    metadata={"trade_date": trade_date.isoformat()},
                )
            )
        else:
            market_bar_gaps = self._market_bar_gaps(trade_date)
            missing_market_bar_count = sum(gap.missing_count for gap in market_bar_gaps)
            for gap in market_bar_gaps:
                issues.append(
                    DataReliabilityIssue(
                        severity="error",
                        check_name="market_bar_gap",
                        source="market_bars",
                        symbol=gap.symbol,
                        message=(
                            f"{gap.symbol} 近 {self._lookback_trade_days} 个交易日"
                            f"缺少 {gap.missing_count} 天行情"
                        ),
                        metadata={"missing_dates": gap.missing_dates},
                    )
                )

        total_sources = len(source_health)
        failed_source_count = len([item for item in source_health if item.failed_snapshots > 0])
        empty_source_count = len([item for item in source_health if item.empty_snapshots > 0])
        return DataReliabilityReport(
            trade_date=trade_date,
            status=self._status(is_trade_date, issues),
            is_trade_date=is_trade_date,
            lookback_trade_days=self._lookback_trade_days,
            total_sources=total_sources,
            failed_source_count=failed_source_count,
            empty_source_count=empty_source_count,
            source_failure_rate=failed_source_count / total_sources if total_sources else 0,
            missing_market_bar_count=missing_market_bar_count,
            source_health=source_health,
            market_bar_gaps=market_bar_gaps,
            issues=issues,
        )

    def _source_health(
        self,
        trade_date: date,
    ) -> tuple[list[DataSourceHealth], list[DataReliabilityIssue]]:
        grouped: dict[str, list[Mapping[str, object]]] = defaultdict(list)
        for row in self.repository.payload_rows("raw_source_snapshots", trade_date=trade_date):
            payload = _payload(row, "raw_source_snapshots")
            grouped[str(payload["source"])].append(payload)

        health: list[DataSourceHealth] = []
        issues: list[DataReliabilityIssue] = []
        for source in sorted(grouped):
            snapshots = grouped[source]
            failed_snapshots = [
                item for item in snapshots if str(item.get("status")) == "failed"
            ]
            empty_snapshots = [
                item
                for item in snapshots
                if str(item.get("status")) == "success" and _int_value(item.get("row_count")) == 0
            ]
            row_count = sum(_int_value(item.get("row_count")) for item in snapshots)
            required = source in self._required_data_sources
            status = self._source_status(
                total=len(snapshots),
                failed=len(failed_snapshots),
                empty=len(empty_snapshots),
            )
            last_failure_reason = _optional_str(
                failed_snapshots[-1].get("failure_reason") if failed_snapshots else None
            )
            health.append(
                DataSourceHealth(
                    source=source,
                    status=status,
                    total_snapshots=len(snapshots),
                    failed_snapshots=len(failed_snapshots),
                    empty_snapshots=len(empty_snapshots),
                    row_count=row_count,
                    failure_rate=len(failed_snapshots) / len(snapshots) if snapshots else 0,
                    last_failure_reason=last_failure_reason,
                    required=required,
                )
            )
            if failed_snapshots:
                severity = "error" if required else "warning"
                issues.append(
                    DataReliabilityIssue(
                        severity=severity,
                        check_name="source_failed",
                        source=source,
                        message=f"{source} 数据源失败 {len(failed_snapshots)} 次",
                        metadata={
                            "failed_snapshots": len(failed_snapshots),
                            "last_failure_reason": last_failure_reason,
                        },
                    )
                )
            if empty_snapshots:
                severity = "error" if required else "warning"
                issues.append(
                    DataReliabilityIssue(
                        severity=severity,
                        check_name="empty_source",
                        source=source,
                        message=f"{source} 数据源空结果 {len(empty_snapshots)} 次",
                        metadata={"empty_snapshots": len(empty_snapshots)},
                    )
                )
        return health, issues

    def _source_status(
        self,
        *,
        total: int,
        failed: int,
        empty: int,
    ) -> SourceHealthStatus:
        if failed == total:
            return "failed"
        if failed > 0:
            return "mixed"
        if empty > 0:
            return "empty"
        return "success"

    def _is_trade_date(self, trade_date: date) -> bool | None:
        rows = self.repository.trading_calendar_days(
            start_date=trade_date,
            end_date=trade_date,
        )
        if not rows:
            return None
        return rows[-1].is_trade_date

    def _market_bar_gaps(self, trade_date: date) -> list[MarketBarGap]:
        expected_dates = self._expected_trade_dates(trade_date)
        if not expected_dates:
            return []
        observed = {
            (str(row.get("symbol") or _payload(row, "market_bars").get("symbol")), _row_date(row))
            for row in self.repository.payload_rows("market_bars")
            if _row_date(row) in set(expected_dates)
        }
        gaps: list[MarketBarGap] = []
        for asset in self._enabled_assets(trade_date):
            missing_dates = [
                item for item in expected_dates if (asset.symbol, item) not in observed
            ]
            if not missing_dates:
                continue
            gaps.append(
                MarketBarGap(
                    symbol=asset.symbol,
                    missing_dates=[item.isoformat() for item in missing_dates],
                    missing_count=len(missing_dates),
                )
            )
        return gaps

    def _expected_trade_dates(self, trade_date: date) -> list[date]:
        calendar_days = self.repository.trading_calendar_days(end_date=trade_date)
        trade_dates = [
            item.calendar_date for item in calendar_days if item.is_trade_date
        ]
        if not trade_dates:
            return [trade_date]
        return sorted(set(trade_dates))[-self._lookback_trade_days :]

    def _enabled_assets(self, trade_date: date) -> list[Asset]:
        latest_by_symbol: dict[str, Mapping[str, object]] = {}
        for row in self.repository.payload_rows("universe_assets"):
            if _row_date(row) > trade_date:
                continue
            payload = _payload(row, "universe_assets")
            symbol = str(row.get("symbol") or payload.get("symbol"))
            latest_by_symbol[symbol] = payload
        assets: list[Asset] = []
        for payload in latest_by_symbol.values():
            if payload.get("enabled", True) is False:
                continue
            asset_type = str(payload.get("asset_type", "ETF"))
            if asset_type not in {"ETF", "STOCK"}:
                continue
            assets.append(
                Asset(
                    symbol=str(payload["symbol"]),
                    name=str(payload["name"]),
                    asset_type=cast(AssetType, asset_type),
                    market=str(payload.get("market", "A_SHARE")),
                    enabled=bool(payload.get("enabled", True)),
                )
            )
        return sorted(assets, key=lambda item: item.symbol)

    def _status(
        self,
        is_trade_date: bool | None,
        issues: list[DataReliabilityIssue],
    ) -> DataReliabilityStatus:
        if any(issue.severity == "error" for issue in issues):
            return "failed"
        if is_trade_date is False:
            return "skipped"
        if issues:
            return "warning"
        return "passed"


def _payload(row: PayloadRecord, table_name: str) -> Mapping[str, object]:
    raw = row.get("payload")
    if not isinstance(raw, Mapping):
        raise ValueError(f"{table_name} payload 必须是 JSON object")
    return cast(Mapping[str, object], raw)


def _row_date(row: PayloadRecord) -> date:
    value = row.get("trade_date")
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value))


def _int_value(value: object) -> int:
    if value is None:
        return 0
    return int(str(value))


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return str(value)
