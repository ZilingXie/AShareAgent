from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal

from ashare_agent.domain import (
    DataQualityIssue,
    DataQualityReport,
    DataQualitySeverity,
    DataQualityStatus,
    MarketBar,
    MarketDataset,
)

_PRE_CLOSE_DAILY_BAR_STAGES = {
    "morning_collect",
    "pre_market",
    "pre_market_brief",
    "intraday_watch",
    "intraday_decision",
}


class DataQualityAgent:
    def __init__(
        self,
        required_data_sources: set[str] | None = None,
        close_jump_threshold: Decimal = Decimal("0.35"),
    ) -> None:
        self._required_data_sources = required_data_sources or set()
        self._close_jump_threshold = close_jump_threshold

    def analyze(self, stage: str, dataset: MarketDataset) -> DataQualityReport:
        issues: list[DataQualityIssue] = []
        issues.extend(self._source_issues(dataset))
        is_trade_date = self._is_trade_date(dataset)
        if is_trade_date is False:
            issues.append(
                DataQualityIssue(
                    severity="warning",
                    check_name="non_trade_date",
                    source="trade_calendar",
                    message=f"{dataset.trade_date.isoformat()} 不是交易日，本次运行仅作提示",
                    metadata={"trade_date": dataset.trade_date.isoformat()},
                )
            )
        expected_market_bar_dates = self._expected_market_bar_dates(stage, dataset)
        market_bar_quality_cutoff = self._market_bar_quality_cutoff(stage, dataset)
        if is_trade_date is not False:
            issues.extend(self._missing_market_bar_issues(dataset, expected_market_bar_dates))
        issues.extend(
            self._abnormal_price_issues(
                [
                    bar
                    for bar in dataset.bars
                    if market_bar_quality_cutoff is not None
                    and bar.trade_date <= market_bar_quality_cutoff
                ]
            )
        )

        total_sources = len(dataset.source_snapshots)
        failed_source_count = sum(
            1 for snapshot in dataset.source_snapshots if snapshot.status == "failed"
        )
        empty_source_count = sum(
            1
            for snapshot in dataset.source_snapshots
            if snapshot.status == "success" and snapshot.row_count == 0
        )
        missing_market_bar_count = sum(
            int(issue.metadata.get("missing_count", 1))
            for issue in issues
            if issue.check_name == "missing_market_bar"
        )
        abnormal_price_count = sum(
            1
            for issue in issues
            if issue.check_name
            in {
                "non_positive_ohlc",
                "invalid_ohlc_range",
                "negative_turnover",
                "abnormal_close_jump",
            }
        )
        status = self._status(issues)
        return DataQualityReport(
            trade_date=dataset.trade_date,
            stage=stage,
            status=status,
            source_failure_rate=failed_source_count / total_sources if total_sources else 0,
            total_sources=total_sources,
            failed_source_count=failed_source_count,
            empty_source_count=empty_source_count,
            missing_market_bar_count=missing_market_bar_count,
            abnormal_price_count=abnormal_price_count,
            is_trade_date=is_trade_date,
            issues=issues,
        )

    def _source_issues(self, dataset: MarketDataset) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        for snapshot in dataset.source_snapshots:
            required = snapshot.source in self._required_data_sources
            if snapshot.status == "failed":
                severity: DataQualitySeverity = "error" if required else "warning"
                issues.append(
                    DataQualityIssue(
                        severity=severity,
                        check_name="source_failed",
                        source=snapshot.source,
                        message=(
                            f"{snapshot.source} 数据源失败: "
                            f"{snapshot.failure_reason or 'unknown failure'}"
                        ),
                        metadata={"row_count": snapshot.row_count},
                    )
                )
            if snapshot.status == "success" and snapshot.row_count == 0:
                severity = "error" if required else "warning"
                issues.append(
                    DataQualityIssue(
                        severity=severity,
                        check_name="empty_source",
                        source=snapshot.source,
                        message=f"{snapshot.source} 数据源返回空结果",
                        metadata={"row_count": snapshot.row_count},
                    )
                )
        return issues

    def _is_trade_date(self, dataset: MarketDataset) -> bool | None:
        if dataset.trade_calendar is not None:
            return dataset.trade_calendar.is_trade_date
        if dataset.trade_calendar_dates:
            return dataset.trade_date in set(dataset.trade_calendar_dates)
        return None

    def _missing_market_bar_issues(
        self,
        dataset: MarketDataset,
        expected_dates: list[date],
    ) -> list[DataQualityIssue]:
        bars_by_symbol = {
            (bar.symbol, bar.trade_date)
            for bar in dataset.bars
            if bar.trade_date in set(expected_dates)
        }
        issues: list[DataQualityIssue] = []
        for asset in dataset.assets:
            if not asset.enabled:
                continue
            missing_dates = [
                expected_date
                for expected_date in expected_dates
                if (asset.symbol, expected_date) not in bars_by_symbol
            ]
            if not missing_dates:
                continue
            issues.append(
                DataQualityIssue(
                    severity="error",
                    check_name="missing_market_bar",
                    source="market_bars",
                    symbol=asset.symbol,
                    message=(
                        f"{asset.symbol} 近 30 个交易日缺少 {len(missing_dates)} 天行情"
                    ),
                    metadata={
                        "trade_date": dataset.trade_date.isoformat(),
                        "missing_dates": [item.isoformat() for item in missing_dates],
                        "missing_count": len(missing_dates),
                    },
                )
            )
        return issues

    def _expected_market_bar_dates(self, stage: str, dataset: MarketDataset) -> list[date]:
        calendar_dates = [
            day.calendar_date
            for day in dataset.trade_calendar_days
            if day.is_trade_date and day.calendar_date <= dataset.trade_date
        ]
        if not calendar_dates:
            calendar_dates = [
                item for item in dataset.trade_calendar_dates if item <= dataset.trade_date
            ]
        if not calendar_dates:
            return [dataset.trade_date]
        calendar_dates = sorted(set(calendar_dates))[-30:]
        if stage in _PRE_CLOSE_DAILY_BAR_STAGES:
            calendar_dates = [item for item in calendar_dates if item < dataset.trade_date]
        return calendar_dates

    def _market_bar_quality_cutoff(self, stage: str, dataset: MarketDataset) -> date | None:
        if stage not in _PRE_CLOSE_DAILY_BAR_STAGES:
            return dataset.trade_date
        calendar_dates = [
            day.calendar_date
            for day in dataset.trade_calendar_days
            if day.is_trade_date and day.calendar_date < dataset.trade_date
        ]
        if not calendar_dates:
            calendar_dates = [
                item for item in dataset.trade_calendar_dates if item < dataset.trade_date
            ]
        if not calendar_dates and (
            dataset.trade_calendar_days or dataset.trade_calendar_dates
        ):
            return None
        if not calendar_dates:
            return dataset.trade_date
        return max(calendar_dates)

    def _abnormal_price_issues(self, bars: list[MarketBar]) -> list[DataQualityIssue]:
        issues: list[DataQualityIssue] = []
        for bar in bars:
            if min(bar.open, bar.high, bar.low, bar.close) <= 0:
                issues.append(
                    self._bar_issue(
                        "non_positive_ohlc",
                        bar,
                        "OHLC 价格必须全部大于 0",
                    )
                )
            if bar.high < max(bar.open, bar.low, bar.close) or bar.low > min(
                bar.open,
                bar.high,
                bar.close,
            ):
                issues.append(
                    self._bar_issue(
                        "invalid_ohlc_range",
                        bar,
                        "high/low 与开收盘价格不一致",
                    )
                )
            if bar.volume < 0 or bar.amount < 0:
                issues.append(
                    self._bar_issue(
                        "negative_turnover",
                        bar,
                        "成交量或成交额不能为负数",
                    )
                )
        issues.extend(self._close_jump_issues(bars))
        return issues

    def _close_jump_issues(self, bars: list[MarketBar]) -> list[DataQualityIssue]:
        grouped: dict[str, list[MarketBar]] = defaultdict(list)
        for bar in bars:
            grouped[bar.symbol].append(bar)
        issues: list[DataQualityIssue] = []
        for symbol_bars in grouped.values():
            ordered = sorted(symbol_bars, key=lambda item: item.trade_date)
            for previous, current in zip(ordered, ordered[1:], strict=False):
                if previous.close <= 0:
                    continue
                jump = abs(current.close - previous.close) / previous.close
                if jump <= self._close_jump_threshold:
                    continue
                issues.append(
                    self._bar_issue(
                        "abnormal_close_jump",
                        current,
                        "相邻收盘价跳变超过 35%",
                        {
                            "previous_trade_date": previous.trade_date.isoformat(),
                            "previous_close": str(previous.close),
                            "current_close": str(current.close),
                            "jump": str(jump),
                        },
                    )
                )
        return issues

    def _bar_issue(
        self,
        check_name: str,
        bar: MarketBar,
        message: str,
        extra_metadata: dict[str, str] | None = None,
    ) -> DataQualityIssue:
        metadata = {
            "trade_date": bar.trade_date.isoformat(),
            "open": str(bar.open),
            "high": str(bar.high),
            "low": str(bar.low),
            "close": str(bar.close),
            "volume": bar.volume,
            "amount": str(bar.amount),
        }
        if extra_metadata is not None:
            metadata.update(extra_metadata)
        return DataQualityIssue(
            severity="error",
            check_name=check_name,
            source="market_bars",
            symbol=bar.symbol,
            message=f"{bar.symbol} {message}",
            metadata=metadata,
        )

    def _status(self, issues: list[DataQualityIssue]) -> DataQualityStatus:
        if any(issue.severity == "error" for issue in issues):
            return "failed"
        if issues:
            return "warning"
        return "passed"
