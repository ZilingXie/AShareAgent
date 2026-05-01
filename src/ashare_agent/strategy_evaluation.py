from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, TypeVar, cast

from yaml import safe_load  # type: ignore[import-untyped]

from ashare_agent.agents.strategy_params_agent import (
    StrategyParams,
    load_strategy_params_from_mapping,
)
from ashare_agent.backtest import BacktestRunner
from ashare_agent.domain import (
    AgentResult,
    AnnouncementItem,
    Asset,
    IndustrySnapshot,
    IntradayBar,
    MarketBar,
    NewsItem,
    PipelineRunContext,
    PolicyItem,
    now_utc,
)
from ashare_agent.llm.base import LLMClient
from ashare_agent.providers.base import DataProvider, DataProviderError
from ashare_agent.reports import MarkdownTable, write_markdown_report
from ashare_agent.repository import PayloadRecord, PipelineRepository

T = TypeVar("T")


@dataclass(frozen=True)
class StrategyEvaluationVariant:
    id: str
    version: str
    label: str
    params: StrategyParams
    overrides: dict[str, Any]


@dataclass(frozen=True)
class StrategyEvaluationConfig:
    base_config: Path
    variants: list[StrategyEvaluationVariant]


@dataclass(frozen=True)
class _CachedFailure:
    error: DataProviderError
    intraday_attempts: list[object] | None = None


@dataclass(frozen=True)
class _CachedIntradayBars:
    bars: list[IntradayBar]
    attempts: list[object]


class CachingDataProvider:
    def __init__(self, provider: DataProvider) -> None:
        self._provider = provider
        self._cache: dict[tuple[object, ...], object] = {}
        self._last_intraday_source_attempts: list[object] = []

    @property
    def intraday_source(self) -> str:
        return str(getattr(self._provider, "intraday_source", "unknown"))

    @property
    def intraday_timeout_seconds(self) -> object:
        return getattr(self._provider, "intraday_timeout_seconds", None)

    @property
    def intraday_retry_attempts(self) -> object:
        return getattr(self._provider, "intraday_retry_attempts", None)

    @property
    def intraday_retry_backoff_seconds(self) -> object:
        return getattr(self._provider, "intraday_retry_backoff_seconds", None)

    @property
    def last_intraday_source_attempts(self) -> list[object]:
        return list(self._last_intraday_source_attempts)

    def _cached(self, key: tuple[object, ...], loader: Callable[[], T]) -> T:
        if key in self._cache:
            value = self._cache[key]
            if isinstance(value, _CachedFailure):
                if value.intraday_attempts is not None:
                    self._last_intraday_source_attempts = list(value.intraday_attempts)
                raise value.error
            return cast(T, value)
        try:
            result = loader()
        except DataProviderError as exc:
            self._cache[key] = _CachedFailure(exc)
            raise
        self._cache[key] = result
        return result

    def get_universe(self) -> list[Asset]:
        return self._cached(("universe",), self._provider.get_universe)

    def get_market_bars(self, trade_date: date, lookback_days: int = 30) -> list[MarketBar]:
        return self._cached(
            ("market_bars", trade_date, lookback_days),
            lambda: self._provider.get_market_bars(trade_date, lookback_days),
        )

    def get_intraday_bars(
        self,
        trade_date: date,
        symbols: list[str],
        period: str = "1",
    ) -> list[IntradayBar]:
        key = ("intraday_bars", trade_date, tuple(sorted(symbols)), period)
        if key in self._cache:
            cached = self._cache[key]
            if isinstance(cached, _CachedFailure):
                self._last_intraday_source_attempts = list(cached.intraday_attempts or [])
                raise cached.error
            if isinstance(cached, _CachedIntradayBars):
                self._last_intraday_source_attempts = list(cached.attempts)
                return cached.bars
            return cast(list[IntradayBar], cached)
        try:
            bars = self._provider.get_intraday_bars(trade_date, symbols, period)
        except DataProviderError as exc:
            attempts = list(getattr(self._provider, "last_intraday_source_attempts", []))
            self._last_intraday_source_attempts = attempts
            self._cache[key] = _CachedFailure(exc, attempts)
            raise
        attempts = list(getattr(self._provider, "last_intraday_source_attempts", []))
        self._last_intraday_source_attempts = attempts
        self._cache[key] = _CachedIntradayBars(bars, attempts)
        return bars

    def get_announcements(self, trade_date: date) -> list[AnnouncementItem]:
        return self._cached(
            ("announcements", trade_date),
            lambda: self._provider.get_announcements(trade_date),
        )

    def get_news(self, trade_date: date) -> list[NewsItem]:
        return self._cached(("news", trade_date), lambda: self._provider.get_news(trade_date))

    def get_policy_items(self, trade_date: date) -> list[PolicyItem]:
        return self._cached(
            ("policy", trade_date),
            lambda: self._provider.get_policy_items(trade_date),
        )

    def get_industry_snapshots(self, trade_date: date) -> list[IndustrySnapshot]:
        return self._cached(
            ("industry", trade_date),
            lambda: self._provider.get_industry_snapshots(trade_date),
        )

    def get_trade_calendar(self) -> list[date]:
        return self._cached(("trade_calendar",), self._provider.get_trade_calendar)


class StrategyEvaluationRunner:
    def __init__(
        self,
        *,
        provider: DataProvider,
        llm_client: LLMClient,
        report_root: Path,
        repository: PipelineRepository,
        strategy_config: StrategyEvaluationConfig,
        provider_name: str,
        required_data_sources: set[str],
        today: date | None = None,
    ) -> None:
        self.provider = (
            provider if isinstance(provider, CachingDataProvider) else CachingDataProvider(provider)
        )
        self.llm_client = llm_client
        self.report_root = report_root
        self.repository = repository
        self.strategy_config = strategy_config
        self.provider_name = provider_name
        self.required_data_sources = required_data_sources
        self.today = today or date.today()

    def run(
        self,
        *,
        evaluation_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AgentResult:
        resolved_id = evaluation_id or f"strategy-eval-{now_utc().strftime('%Y%m%d%H%M%S')}"
        resolved_start, resolved_end = self._resolve_window(start_date, end_date)
        variant_payloads: list[dict[str, Any]] = []
        for variant in self.strategy_config.variants:
            backtest_id = f"{resolved_id}-{variant.id}"
            runner = BacktestRunner(
                provider=self.provider,
                llm_client=self.llm_client,
                report_root=self.report_root,
                repository=self.repository,
                strategy_params=variant.params,
                provider_name=self.provider_name,
                required_data_sources=self.required_data_sources,
            )
            try:
                result = runner.run(
                    start_date=resolved_start,
                    end_date=resolved_end,
                    backtest_id=backtest_id,
                )
                metrics = self._metrics_for_backtest(
                    backtest_id=backtest_id,
                    backtest_payload=result.payload,
                    params=variant.params,
                )
                variant_payloads.append(
                    {
                        "id": variant.id,
                        "version": variant.version,
                        "label": variant.label,
                        "backtest_id": backtest_id,
                        "success": result.success,
                        **metrics,
                    }
                )
            except DataProviderError as exc:
                variant_payloads.append(
                    self._variant_failure_payload(
                        variant=variant,
                        backtest_id=backtest_id,
                        reason=str(exc),
                    )
                )

        recommendation = self._recommendation(variant_payloads)
        report_path = self._write_report(
            evaluation_id=resolved_id,
            start_date=resolved_start,
            end_date=resolved_end,
            variants=variant_payloads,
            recommendation=recommendation,
        )
        payload: dict[str, Any] = {
            "evaluation_id": resolved_id,
            "provider": self.provider_name,
            "start_date": resolved_start.isoformat(),
            "end_date": resolved_end.isoformat(),
            "variant_count": len(variant_payloads),
            "variants": variant_payloads,
            "recommendation": recommendation,
            "report_path": str(report_path),
        }
        context = PipelineRunContext(
            trade_date=resolved_end,
            run_mode="backtest",
            backtest_id=resolved_id,
        )
        self.repository.save_artifact(resolved_end, "strategy_evaluation", payload)
        self.repository.save_pipeline_run(context, "strategy_evaluation", "success", payload)
        return AgentResult(name="strategy_evaluation", success=True, payload=payload)

    def _resolve_window(
        self,
        start_date: date | None,
        end_date: date | None,
    ) -> tuple[date, date]:
        if (start_date is None) != (end_date is None):
            raise ValueError("--start-date 和 --end-date 必须同时提供")
        if start_date is not None and end_date is not None:
            if start_date > end_date:
                raise ValueError("start_date 不能晚于 end_date")
            return start_date, end_date
        trade_days = sorted(day for day in self.provider.get_trade_calendar() if day <= self.today)
        if len(trade_days) < 10:
            raise DataProviderError("交易日历不足 10 个交易日，无法生成默认评估窗口")
        return trade_days[-10], trade_days[-1]

    def _variant_failure_payload(
        self,
        *,
        variant: StrategyEvaluationVariant,
        backtest_id: str,
        reason: str,
    ) -> dict[str, Any]:
        return {
            "id": variant.id,
            "version": variant.version,
            "label": variant.label,
            "backtest_id": backtest_id,
            "success": False,
            "attempted_days": 0,
            "succeeded_days": 0,
            "failed_days": 0,
            "failures": [{"reason": reason}],
            "source_failure_rate": 1.0,
            "data_quality_failure_rate": 1.0,
            "signal_count": 0,
            "risk_approved_count": 0,
            "risk_rejected_count": 0,
            "risk_reject_reasons": {},
            "order_count": 0,
            "buy_order_count": 0,
            "sell_order_count": 0,
            "execution_event_count": 0,
            "execution_failed_count": 0,
            "execution_failure_reasons": {},
            "closed_trade_count": 0,
            "signal_hit_count": 0,
            "signal_hit_rate": 0.0,
            "open_position_count": 0,
            "holding_pnl": "0",
            "total_return": 0.0,
            "max_drawdown": 0.0,
        }

    def _metrics_for_backtest(
        self,
        *,
        backtest_id: str,
        backtest_payload: Mapping[str, object],
        params: StrategyParams,
    ) -> dict[str, Any]:
        attempted_days = _int_value(backtest_payload.get("attempted_days", 0))
        failed_days = _int_value(backtest_payload.get("failed_days", 0))
        pipeline_rows = self._scoped_rows("pipeline_runs", backtest_id)
        signal_rows = self._scoped_rows("signals", backtest_id)
        risk_rows = self._scoped_rows("risk_decisions", backtest_id)
        order_rows = self._scoped_rows("paper_orders", backtest_id)
        position_rows = self._scoped_rows("paper_positions", backtest_id)
        portfolio_rows = self._scoped_rows("portfolio_snapshots", backtest_id)
        source_rows = self._scoped_rows("raw_source_snapshots", backtest_id)
        quality_rows = self._scoped_rows("data_quality_reports", backtest_id)

        approved_count = 0
        rejected_count = 0
        reject_reasons: Counter[str] = Counter()
        for row in risk_rows:
            payload = _payload(row)
            if bool(payload.get("approved")):
                approved_count += 1
            else:
                rejected_count += 1
                reject_reasons.update(_string_values(payload.get("reasons", [])))

        buy_count = 0
        sell_count = 0
        for row in order_rows:
            payload = _payload(row)
            if payload.get("side") == "buy":
                buy_count += 1
            elif payload.get("side") == "sell":
                sell_count += 1

        execution_events: list[Mapping[str, object]] = []
        for row in pipeline_rows:
            payload = _payload(row)
            if payload.get("stage") != "intraday_watch":
                continue
            raw_events = payload.get("execution_events", [])
            if isinstance(raw_events, list):
                for event in cast(list[object], raw_events):
                    if isinstance(event, Mapping):
                        execution_events.append(cast(Mapping[str, object], event))
        execution_reasons = Counter(
            str(event.get("failure_reason"))
            for event in execution_events
            if event.get("status") == "rejected" and event.get("failure_reason")
        )

        closed_trade_count, signal_hit_count, open_position_count, holding_pnl = (
            self._position_metrics(position_rows)
        )
        total_return = self._total_return(portfolio_rows, params.paper_trader.initial_cash)
        max_drawdown = self._max_drawdown(portfolio_rows)
        failed_source_count = sum(
            1 for row in source_rows if _payload(row).get("status") == "failed"
        )
        source_failure_rate = (
            failed_source_count / len(source_rows) if source_rows else 0.0
        )
        failed_quality_dates = {
            str(row["trade_date"])
            for row in quality_rows
            if _payload(row).get("status") == "failed"
        }
        data_quality_failure_rate = (
            len(failed_quality_dates) / attempted_days if attempted_days else 0.0
        )
        signal_hit_rate = signal_hit_count / closed_trade_count if closed_trade_count else 0.0
        return {
            "attempted_days": attempted_days,
            "succeeded_days": _int_value(backtest_payload.get("succeeded_days", 0)),
            "failed_days": failed_days,
            "failures": backtest_payload.get("failures", []),
            "source_failure_rate": source_failure_rate,
            "data_quality_failure_rate": data_quality_failure_rate,
            "signal_count": len(signal_rows),
            "risk_approved_count": approved_count,
            "risk_rejected_count": rejected_count,
            "risk_reject_reasons": dict(sorted(reject_reasons.items())),
            "order_count": len(order_rows),
            "buy_order_count": buy_count,
            "sell_order_count": sell_count,
            "execution_event_count": len(execution_events),
            "execution_failed_count": sum(
                1 for event in execution_events if event.get("status") == "rejected"
            ),
            "execution_failure_reasons": dict(sorted(execution_reasons.items())),
            "closed_trade_count": closed_trade_count,
            "signal_hit_count": signal_hit_count,
            "signal_hit_rate": signal_hit_rate,
            "open_position_count": open_position_count,
            "holding_pnl": str(holding_pnl.quantize(Decimal("0.01"))),
            "total_return": total_return,
            "max_drawdown": max_drawdown,
        }

    def _scoped_rows(self, table_name: str, backtest_id: str) -> list[PayloadRecord]:
        rows = self.repository.payload_rows(table_name)
        return [
            row
            for row in rows
            if _payload(row).get("run_mode") == "backtest"
            and _payload(row).get("backtest_id") == backtest_id
        ]

    def _position_metrics(
        self,
        position_rows: list[PayloadRecord],
    ) -> tuple[int, int, int, Decimal]:
        latest_by_position: dict[tuple[str, str], Mapping[str, object]] = {}
        for row in position_rows:
            payload = _payload(row)
            symbol = str(payload.get("symbol", ""))
            opened_at = str(payload.get("opened_at", ""))
            if not symbol or not opened_at:
                continue
            latest_by_position[(symbol, opened_at)] = payload
        closed_trade_count = 0
        signal_hit_count = 0
        open_position_count = 0
        holding_pnl = Decimal("0")
        for payload in latest_by_position.values():
            quantity = _decimal(payload.get("quantity", "0"))
            entry_price = _decimal(payload.get("entry_price", "0"))
            if payload.get("status") == "closed":
                exit_price = _decimal(payload.get("exit_price", payload.get("current_price", "0")))
                pnl = (exit_price - entry_price) * quantity
                holding_pnl += pnl
                closed_trade_count += 1
                if pnl > 0:
                    signal_hit_count += 1
            elif payload.get("status") == "open":
                current_price = _decimal(payload.get("current_price", "0"))
                holding_pnl += (current_price - entry_price) * quantity
                open_position_count += 1
        return closed_trade_count, signal_hit_count, open_position_count, holding_pnl

    def _total_return(
        self,
        portfolio_rows: list[PayloadRecord],
        initial_cash: Decimal,
    ) -> float:
        if not portfolio_rows or initial_cash <= 0:
            return 0.0
        final_payload = _payload(portfolio_rows[-1])
        total_value = _decimal(final_payload.get("total_value", initial_cash))
        return float((total_value - initial_cash) / initial_cash)

    def _max_drawdown(self, portfolio_rows: list[PayloadRecord]) -> float:
        peak: Decimal | None = None
        max_drawdown = Decimal("0")
        for row in portfolio_rows:
            total_value = _decimal(_payload(row).get("total_value", "0"))
            if total_value <= 0:
                continue
            if peak is None or total_value > peak:
                peak = total_value
                continue
            drawdown = (peak - total_value) / peak
            if drawdown > max_drawdown:
                max_drawdown = drawdown
        return float(max_drawdown)

    def _recommendation(self, variants: list[dict[str, Any]]) -> dict[str, Any]:
        if not variants:
            return {"summary": "无 variant 可评估", "recommended_variant_ids": []}
        baseline = variants[0]
        recommended: list[str] = []
        for variant in variants[1:]:
            if (
                float(variant.get("total_return", 0)) > float(baseline.get("total_return", 0))
                and float(variant.get("signal_hit_rate", 0))
                >= float(baseline.get("signal_hit_rate", 0))
                and float(variant.get("max_drawdown", 0))
                <= float(baseline.get("max_drawdown", 0))
                and int(variant.get("failed_days", 0)) <= int(baseline.get("failed_days", 0))
                and float(variant.get("source_failure_rate", 0))
                <= float(baseline.get("source_failure_rate", 0))
            ):
                recommended.append(str(variant["id"]))
        if recommended:
            summary = "可考虑人工复核后替换参数: " + ", ".join(recommended)
        else:
            summary = "未发现同时改善收益/命中率且不恶化回撤和失败率的参数组合"
        return {"summary": summary, "recommended_variant_ids": recommended}

    def _write_report(
        self,
        *,
        evaluation_id: str,
        start_date: date,
        end_date: date,
        variants: list[dict[str, Any]],
        recommendation: Mapping[str, object],
    ) -> Path:
        ranking = sorted(
            variants,
            key=lambda item: (
                float(item.get("total_return", 0)),
                float(item.get("signal_hit_rate", 0)),
            ),
            reverse=True,
        )
        return write_markdown_report(
            self.report_root,
            evaluation_id,
            "strategy-evaluation.md",
            {
                "评估范围": [
                    f"evaluation_id: {evaluation_id}",
                    f"start_date: {start_date.isoformat()}",
                    f"end_date: {end_date.isoformat()}",
                    f"provider: {self.provider_name}",
                    "LLM: mock",
                ],
                "Variant 排名": MarkdownTable(
                    headers=[
                        "id",
                        "label",
                        "return",
                        "hit_rate",
                        "drawdown",
                        "failed_days",
                        "orders",
                    ],
                    rows=[
                        [
                            item["id"],
                            item["label"],
                            f"{float(item.get('total_return', 0)):.2%}",
                            f"{float(item.get('signal_hit_rate', 0)):.2%}",
                            f"{float(item.get('max_drawdown', 0)):.2%}",
                            item.get("failed_days", 0),
                            item.get("order_count", 0),
                        ]
                        for item in ranking
                    ],
                ),
                "关键指标": MarkdownTable(
                    headers=[
                        "id",
                        "signals",
                        "risk_pass",
                        "risk_reject",
                        "exec_failed",
                        "closed",
                        "open",
                        "pnl",
                    ],
                    rows=[
                        [
                            item["id"],
                            item.get("signal_count", 0),
                            item.get("risk_approved_count", 0),
                            item.get("risk_rejected_count", 0),
                            item.get("execution_failed_count", 0),
                            item.get("closed_trade_count", 0),
                            item.get("open_position_count", 0),
                            item.get("holding_pnl", "0"),
                        ]
                        for item in variants
                    ],
                ),
                "调整建议": str(recommendation.get("summary", "")),
                "安全边界": "本报告只基于历史模拟回放，不自动修改策略参数，不构成投资建议。",
            },
        )


def load_strategy_evaluation_config(config_path: Path) -> StrategyEvaluationConfig:
    if not config_path.exists():
        raise FileNotFoundError(f"策略评估配置不存在: {config_path}")
    raw_data = cast(object, safe_load(config_path.read_text(encoding="utf-8")))
    if not isinstance(raw_data, dict):
        raise ValueError("策略评估配置必须是 YAML object")
    raw = cast(dict[str, object], raw_data)
    base_config_value = raw.get("base_config")
    if not isinstance(base_config_value, str) or not base_config_value.strip():
        raise ValueError("策略评估配置缺少 base_config")
    base_config_path = _resolve_config_path(config_path, base_config_value)
    base_raw = _load_base_strategy_config(base_config_path)
    raw_variants = raw.get("variants")
    if not isinstance(raw_variants, list) or not raw_variants:
        raise ValueError("策略评估配置必须包含 variants 列表")

    variants: list[StrategyEvaluationVariant] = []
    seen_ids: set[str] = set()
    seen_versions: set[str] = set()
    for item in cast(list[object], raw_variants):
        if not isinstance(item, dict):
            raise ValueError("variants 中每一项必须是 object")
        row = cast(dict[str, object], item)
        variant_id = _required_variant_str(row, "id")
        version = _required_variant_str(row, "version")
        label = str(row.get("label") or variant_id).strip()
        if not label:
            raise ValueError(f"variant {variant_id} label 不能为空")
        if variant_id in seen_ids:
            raise ValueError(f"variant id 重复: {variant_id}")
        if version in seen_versions:
            raise ValueError(f"variant version 重复: {version}")
        seen_ids.add(variant_id)
        seen_versions.add(version)
        overrides_data = row.get("overrides", {})
        if not isinstance(overrides_data, dict):
            raise ValueError(f"variant {variant_id} overrides 必须是 object")
        overrides = cast(dict[str, object], overrides_data)
        merged = _deep_merge(base_raw, overrides)
        merged["version"] = version
        try:
            params = load_strategy_params_from_mapping(merged)
        except ValueError as exc:
            raise ValueError(f"variant {variant_id} 策略参数非法: {exc}") from exc
        variants.append(
            StrategyEvaluationVariant(
                id=variant_id,
                version=version,
                label=label,
                params=params,
                overrides=cast(dict[str, Any], deepcopy(overrides)),
            )
        )
    return StrategyEvaluationConfig(base_config=base_config_path, variants=variants)


def _resolve_config_path(config_path: Path, value: str) -> Path:
    candidate = Path(value).expanduser()
    if candidate.is_absolute() or candidate.exists():
        return candidate
    relative_to_config = config_path.parent / candidate
    if relative_to_config.exists():
        return relative_to_config
    return candidate


def _load_base_strategy_config(path: Path) -> dict[str, object]:
    if not path.exists():
        raise FileNotFoundError(f"基础策略参数配置不存在: {path}")
    raw_data = cast(object, safe_load(path.read_text(encoding="utf-8")))
    if not isinstance(raw_data, dict):
        raise ValueError("基础策略参数配置必须是 YAML object")
    return cast(dict[str, object], raw_data)


def _required_variant_str(raw: Mapping[str, object], field_name: str) -> str:
    value = str(raw.get(field_name, "")).strip()
    if not value:
        raise ValueError(f"variant {field_name} 不能为空")
    return value


def _deep_merge(
    base: Mapping[str, object],
    overrides: Mapping[str, object],
    path: str = "",
) -> dict[str, object]:
    result = deepcopy(dict(base))
    for key, value in overrides.items():
        field_path = f"{path}.{key}" if path else str(key)
        if key not in base:
            raise ValueError(f"未知策略参数字段: {field_path}")
        base_value = base[key]
        if isinstance(base_value, Mapping):
            if not isinstance(value, Mapping):
                raise ValueError(f"策略参数字段 {field_path} 必须是 object")
            result[str(key)] = _deep_merge(
                cast(Mapping[str, object], base_value),
                cast(Mapping[str, object], value),
                field_path,
            )
            continue
        if isinstance(value, Mapping):
            raise ValueError(f"策略参数字段 {field_path} 不能是 object")
        result[str(key)] = deepcopy(value)
    return result


def _payload(row: PayloadRecord) -> Mapping[str, object]:
    payload = row.get("payload")
    if not isinstance(payload, Mapping):
        raise ValueError("payload 必须是 JSON object")
    return cast(Mapping[str, object], payload)


def _string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in cast(list[object], value) if str(item)]


def _decimal(value: object) -> Decimal:
    return Decimal(str(value))


def _int_value(value: object) -> int:
    return int(str(value))
