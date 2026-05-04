from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Protocol, cast

from ashare_agent.agents.dashboard_query_agent import DashboardQueryAgent
from ashare_agent.agents.strategy_params_agent import (
    StrategyParams,
    load_strategy_params_from_mapping,
)
from ashare_agent.domain import AgentResult, PipelineRunContext, now_utc
from ashare_agent.llm.base import LLMClient
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.base import DataProvider
from ashare_agent.reports import MarkdownTable, write_markdown_report
from ashare_agent.repository import PipelineRepository
from ashare_agent.strategy_evaluation import (
    CachingDataProvider,
    StrategyEvaluationConfig,
    StrategyEvaluationRunner,
    StrategyEvaluationVariant,
)


class StrategyInsightLLMClient(Protocol):
    def generate_strategy_insight(
        self,
        trade_date: date,
        context: dict[str, Any],
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True)
class StrategyInsightNarrative:
    model: str
    summary: str
    attribution: list[str]
    hypotheses: list[dict[str, Any]]
    recommended_experiments: list[dict[str, Any]]
    raw_response: dict[str, Any]


@dataclass(frozen=True)
class HypothesisVariantBuildResult:
    variants: list[StrategyEvaluationVariant]
    experiments: list[dict[str, Any]]


@dataclass(frozen=True)
class StrategyInsightGateResult:
    recommended_variant_ids: list[str]
    passed_window_count_by_variant: dict[str, int]
    failed_variant_reasons_by_window: dict[str, dict[str, list[str]]]


class StrategyEvaluationRunnerLike(Protocol):
    def run(
        self,
        *,
        evaluation_id: str | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
    ) -> AgentResult: ...


class EvaluationRunnerClass(Protocol):
    def __call__(
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
    ) -> StrategyEvaluationRunnerLike: ...


class StrategyInsightAgent:
    def __init__(self, llm_client: LLMClient | StrategyInsightLLMClient) -> None:
        self.llm_client = llm_client

    def generate(self, *, trade_date: date, context: dict[str, Any]) -> StrategyInsightNarrative:
        if not hasattr(self.llm_client, "generate_strategy_insight"):
            raise ValueError("当前 LLM client 不支持 strategy insight JSON 生成")
        raw_response = cast(StrategyInsightLLMClient, self.llm_client).generate_strategy_insight(
            trade_date,
            context,
        )
        model = str(raw_response.get("model", "unknown"))
        raw_content = raw_response.get("content")
        parsed: Mapping[str, object]
        if raw_content is None:
            parsed = raw_response
        else:
            try:
                parsed_raw = json.loads(str(raw_content))
            except json.JSONDecodeError as exc:
                raise ValueError("strategy insight JSON 解析失败") from exc
            if not isinstance(parsed_raw, Mapping):
                raise ValueError("strategy insight JSON 必须是 object")
            parsed = cast(Mapping[str, object], parsed_raw)
        return StrategyInsightNarrative(
            model=model,
            summary=_required_json_str(parsed, "summary"),
            hypotheses=_required_json_object_list(parsed, "hypotheses"),
            attribution=_required_json_str_list(parsed, "attribution"),
            recommended_experiments=_required_json_object_list(
                parsed,
                "recommended_experiments",
            ),
            raw_response=dict(raw_response),
        )


class HypothesisVariantBuilder:
    def __init__(self, base_params: StrategyParams) -> None:
        self.base_params = base_params
        self.base_snapshot = base_params.snapshot()

    def build(self, insight: StrategyInsightNarrative) -> HypothesisVariantBuildResult:
        experiments: list[dict[str, Any]] = []
        variants = [
            StrategyEvaluationVariant(
                id="baseline",
                version=f"{self.base_params.version}-baseline",
                label="当前参数",
                params=self.base_params,
                overrides={},
            )
        ]
        seen_variant_ids = {"baseline"}
        for item in insight.recommended_experiments:
            experiment = self._compile_experiment(item)
            experiments.append(experiment)
            if experiment["policy_status"] != "approved":
                continue
            variant_id = str(experiment["variant_id"])
            if variant_id in seen_variant_ids:
                experiment["policy_status"] = "rejected_by_policy"
                experiment["policy_reason"] = f"variant id 重复: {variant_id}"
                continue
            overrides = cast(dict[str, Any], experiment["overrides"])
            merged = _deep_merge(cast(dict[str, object], self.base_snapshot), overrides)
            merged["version"] = f"{self.base_params.version}-{variant_id}"
            params = load_strategy_params_from_mapping(merged)
            variants.append(
                StrategyEvaluationVariant(
                    id=variant_id,
                    version=str(merged["version"]),
                    label=str(experiment["name"]),
                    params=params,
                    overrides=overrides,
                )
            )
            seen_variant_ids.add(variant_id)
        return HypothesisVariantBuildResult(variants=variants, experiments=experiments)

    def _compile_experiment(self, item: Mapping[str, object]) -> dict[str, Any]:
        name = str(item.get("name") or "").strip()
        param = str(item.get("param") or "").strip()
        if not name:
            name = param or "未命名实验"
        candidate_value = item.get("candidate_value")
        experiment: dict[str, Any] = {
            "name": name,
            "param": param,
            "candidate_value": str(candidate_value),
            "policy_status": "rejected_by_policy",
            "policy_reason": None,
            "variant_id": None,
            "overrides": {},
        }
        try:
            normalized_param, overrides = self._overrides_for(param, candidate_value)
        except ValueError as exc:
            experiment["policy_reason"] = str(exc)
            return experiment
        variant_id = _variant_id(normalized_param, _candidate_value_for_id(overrides))
        experiment.update(
            {
                "param": normalized_param,
                "policy_status": "approved",
                "variant_id": variant_id,
                "overrides": overrides,
            }
        )
        return experiment

    def _overrides_for(self, param: str, value: object) -> tuple[str, dict[str, Any]]:
        if param == "paper_trader.max_positions":
            param = "risk.max_positions"
        if param == "signal.min_score":
            candidate = _float_between(value, param, minimum=0.30, maximum=0.90)
            return param, {"signal": {"min_score": _float_text(candidate)}}
        if param == "signal.weights.technical":
            candidate = _float_between(value, param, minimum=0.0, maximum=1.0)
            return param, {"signal": {"weights": {"technical": _float_text(candidate)}}}
        if param == "signal.weights.market":
            candidate = _float_between(value, param, minimum=0.0, maximum=1.0)
            return param, {"signal": {"weights": {"market": _float_text(candidate)}}}
        if param == "risk.stop_loss_pct":
            candidate = _decimal_between(
                value,
                param,
                minimum=Decimal("0.02"),
                maximum=Decimal("0.10"),
            )
            return param, {"risk": {"stop_loss_pct": str(candidate)}}
        if param == "risk.min_holding_trade_days":
            candidate = _int_between(value, param, minimum=1, maximum=5)
            if candidate > self.base_params.risk.max_holding_trade_days:
                raise ValueError(
                    "risk.min_holding_trade_days 不能大于当前 "
                    "risk.max_holding_trade_days"
                )
            return param, {"risk": {"min_holding_trade_days": candidate}}
        if param == "risk.max_holding_trade_days":
            candidate = _int_between(value, param, minimum=2, maximum=20)
            if candidate < self.base_params.risk.min_holding_trade_days:
                raise ValueError(
                    "risk.max_holding_trade_days 不能小于当前 "
                    "risk.min_holding_trade_days"
                )
            return param, {"risk": {"max_holding_trade_days": candidate}}
        if param == "risk.max_positions":
            candidate = _int_between(value, param, minimum=1, maximum=5)
            return param, {"risk": {"max_positions": candidate}}
        raise ValueError(f"参数不在策略优化白名单: {param}")


class StrategyInsightGate:
    def evaluate(
        self,
        window_payloads: list[Mapping[str, object]],
    ) -> StrategyInsightGateResult:
        passed_counts: dict[str, int] = defaultdict(int)
        failed_by_window: dict[str, dict[str, list[str]]] = {}
        for window_payload in window_payloads:
            evaluation_id = str(window_payload.get("evaluation_id", ""))
            variants = _mapping_list(window_payload.get("variants", []))
            if len(variants) < 2:
                continue
            baseline = variants[0]
            failed_by_window[evaluation_id] = {}
            for variant in variants[1:]:
                variant_id = str(variant.get("id", ""))
                reasons = self._variant_reasons(variant, baseline)
                failed_by_window[evaluation_id][variant_id] = reasons
                if not reasons:
                    passed_counts[variant_id] += 1
        recommended = sorted(
            variant_id for variant_id, count in passed_counts.items() if count >= 2
        )
        return StrategyInsightGateResult(
            recommended_variant_ids=recommended,
            passed_window_count_by_variant=dict(sorted(passed_counts.items())),
            failed_variant_reasons_by_window=failed_by_window,
        )

    def _variant_reasons(
        self,
        variant: Mapping[str, object],
        baseline: Mapping[str, object],
    ) -> list[str]:
        reasons: list[str] = []
        if _float(variant.get("total_return")) < _float(baseline.get("total_return")):
            reasons.append("收益低于基准")
        if _float(variant.get("max_drawdown")) > _float(baseline.get("max_drawdown")):
            reasons.append("最大回撤高于基准")
        if _float(variant.get("data_quality_failure_rate")) > _float(
            baseline.get("data_quality_failure_rate")
        ):
            reasons.append("数据质量失败率高于基准")
        baseline_attempted = max(_int(baseline.get("attempted_days")), 1)
        variant_attempted = max(_int(variant.get("attempted_days")), 1)
        baseline_exec_rate = _int(baseline.get("execution_failed_count")) / baseline_attempted
        variant_exec_rate = _int(variant.get("execution_failed_count")) / variant_attempted
        if variant_exec_rate - baseline_exec_rate > 0.05:
            reasons.append("成交失败率明显高于基准")
        baseline_orders = _int(baseline.get("order_count"))
        variant_orders = _int(variant.get("order_count"))
        if variant_orders > max(baseline_orders * 2, baseline_orders + 3):
            reasons.append("订单数异常暴增")
        return reasons


class StrategyInsightRunner:
    def __init__(
        self,
        *,
        provider: DataProvider,
        llm_client: LLMClient | StrategyInsightLLMClient,
        report_root: Path,
        repository: PipelineRepository,
        strategy_params: StrategyParams,
        provider_name: str,
        required_data_sources: set[str],
        evaluation_runner_class: EvaluationRunnerClass = StrategyEvaluationRunner,
    ) -> None:
        self.provider = (
            provider if isinstance(provider, CachingDataProvider) else CachingDataProvider(provider)
        )
        self.llm_client = llm_client
        self.report_root = report_root
        self.repository = repository
        self.strategy_params = strategy_params
        self.provider_name = provider_name
        self.required_data_sources = required_data_sources
        self.evaluation_runner_class = evaluation_runner_class

    def run(self, *, trade_date: date, insight_id: str | None = None) -> AgentResult:
        resolved_id = insight_id or f"strategy-insight-{now_utc().strftime('%Y%m%d%H%M%S')}"
        context = PipelineRunContext(trade_date=trade_date)
        insight_context = self._insight_context(trade_date)
        narrative = StrategyInsightAgent(self.llm_client).generate(
            trade_date=trade_date,
            context=insight_context,
        )
        build = HypothesisVariantBuilder(self.strategy_params).build(narrative)
        approved_variants = [
            variant for variant in build.variants if variant.id != "baseline"
        ]
        evaluation_windows: list[dict[str, Any]] = []
        evaluation_payloads: list[Mapping[str, object]] = []
        if approved_variants:
            for window in (20, 40, 60):
                evaluation_id = f"{resolved_id}-{window}d"
                evaluation_config = StrategyEvaluationConfig(
                    base_config=Path("configs/strategy_params.yml"),
                    variants=build.variants,
                    default_window_trade_days=window,
                )
                runner = self.evaluation_runner_class(
                    provider=self.provider,
                    llm_client=MockLLMClient(),
                    report_root=self.report_root,
                    repository=self.repository,
                    strategy_config=evaluation_config,
                    provider_name=self.provider_name,
                    required_data_sources=self.required_data_sources,
                    today=trade_date,
                )
                result = runner.run(evaluation_id=evaluation_id)
                evaluation_payloads.append(result.payload)
        gate = StrategyInsightGate().evaluate(evaluation_payloads)
        for evaluation_payload in evaluation_payloads:
            evaluation_id = str(evaluation_payload.get("evaluation_id", ""))
            recommendation = cast(
                Mapping[str, object],
                evaluation_payload.get("recommendation", {}),
            )
            evaluation_windows.append(
                {
                    "window_trade_days": _window_from_evaluation_id(evaluation_id),
                    "evaluation_id": evaluation_id,
                    "report_path": str(evaluation_payload.get("report_path", "")),
                    "recommended_variant_ids": _string_list(
                        recommendation.get("recommended_variant_ids", []),
                    ),
                    "passed_variant_ids": [
                        variant_id
                        for variant_id, reasons in gate.failed_variant_reasons_by_window.get(
                            evaluation_id,
                            {},
                        ).items()
                        if not reasons
                    ],
                    "failed_variant_reasons": gate.failed_variant_reasons_by_window.get(
                        evaluation_id,
                        {},
                    ),
                }
            )
        report_path = self._write_report(
            insight_id=resolved_id,
            trade_date=trade_date,
            narrative=narrative,
            experiments=build.experiments,
            evaluation_windows=evaluation_windows,
            gate=gate,
        )
        payload: dict[str, Any] = {
            "insight_id": resolved_id,
            "trade_date": trade_date.isoformat(),
            "provider": self.provider_name,
            "llm_model": narrative.model,
            "summary": narrative.summary,
            "attribution": narrative.attribution,
            "hypotheses": narrative.hypotheses,
            "experiments": build.experiments,
            "evaluation_windows": evaluation_windows,
            "gate_summary": asdict(gate),
            "recommended_variant_ids": gate.recommended_variant_ids,
            "manual_status": "pending_review",
            "report_path": str(report_path),
            "real_trading": False,
        }
        self.repository.save_artifact(trade_date, "strategy_insight", payload)
        self.repository.save_pipeline_run(context, "strategy_insight", "success", payload)
        return AgentResult(name="strategy_insight", success=True, payload=payload)

    def _insight_context(self, trade_date: date) -> dict[str, Any]:
        query = DashboardQueryAgent(self.repository)
        day_summary = query.day_summary(trade_date)
        evaluations = query.list_strategy_evaluations(limit=5)
        return {
            "day_summary": asdict(day_summary),
            "recent_strategy_evaluations": [asdict(item) for item in evaluations],
            "strategy_params_snapshot": self.strategy_params.snapshot(),
        }

    def _write_report(
        self,
        *,
        insight_id: str,
        trade_date: date,
        narrative: StrategyInsightNarrative,
        experiments: list[dict[str, Any]],
        evaluation_windows: list[dict[str, Any]],
        gate: StrategyInsightGateResult,
    ) -> Path:
        return write_markdown_report(
            self.report_root,
            insight_id,
            "strategy-insights.md",
            {
                "复盘摘要": narrative.summary,
                "归因": narrative.attribution,
                "假设": MarkdownTable(
                    headers=["area", "direction", "reason", "risk"],
                    rows=[
                        [
                            _table_cell(item, "area"),
                            _table_cell(item, "direction"),
                            _table_cell(item, "reason"),
                            _table_cell(item, "risk"),
                        ]
                        for item in _dict_mappings(narrative.hypotheses)
                    ],
                ),
                "实验编译": MarkdownTable(
                    headers=["name", "param", "candidate", "status", "reason"],
                    rows=[
                        [
                            _table_cell(item, "name"),
                            _table_cell(item, "param"),
                            _table_cell(item, "candidate_value"),
                            _table_cell(item, "policy_status"),
                            _table_cell(item, "policy_reason"),
                        ]
                        for item in _dict_mappings(experiments)
                    ],
                ),
                "多窗口评估": MarkdownTable(
                    headers=["window", "evaluation_id", "passed", "recommended", "report"],
                    rows=[
                        [
                            _table_cell(item, "window_trade_days"),
                            _table_cell(item, "evaluation_id"),
                            ", ".join(_string_list(item.get("passed_variant_ids", []))),
                            ", ".join(_string_list(item.get("recommended_variant_ids", []))),
                            _table_cell(item, "report_path"),
                        ]
                        for item in _dict_mappings(evaluation_windows)
                    ],
                ),
                "门槛结论": [
                    "可人工复核候选: "
                    + (
                        ", ".join(gate.recommended_variant_ids)
                        if gate.recommended_variant_ids
                        else "无"
                    ),
                    f"trade_date: {trade_date.isoformat()}",
                    "manual_status: pending_review",
                ],
                "安全边界": "LLM 只提出假设；本流程不自动修改策略参数，不生成真实交易。",
            },
        )


def _required_json_str(payload: Mapping[str, object], field_name: str) -> str:
    value = payload.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"strategy insight JSON 缺少 {field_name}")
    return value


def _required_json_str_list(payload: Mapping[str, object], field_name: str) -> list[str]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"strategy insight JSON 字段 {field_name} 必须是 string list")
    values = cast(list[object], value)
    if not all(isinstance(item, str) for item in values):
        raise ValueError(f"strategy insight JSON 字段 {field_name} 必须是 string list")
    return cast(list[str], values)


def _required_json_object_list(
    payload: Mapping[str, object],
    field_name: str,
) -> list[dict[str, Any]]:
    value = payload.get(field_name)
    if not isinstance(value, list):
        raise ValueError(f"strategy insight JSON 字段 {field_name} 必须是 object list")
    values = cast(list[object], value)
    if not all(isinstance(item, Mapping) for item in values):
        raise ValueError(f"strategy insight JSON 字段 {field_name} 必须是 object list")
    return [dict(cast(Mapping[str, object], item)) for item in values]


def _float_between(value: object, field_name: str, *, minimum: float, maximum: float) -> float:
    try:
        candidate = float(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是数字") from exc
    if candidate < minimum or candidate > maximum:
        raise ValueError(f"{field_name} 必须在 {minimum} 到 {maximum} 之间")
    return candidate


def _decimal_between(
    value: object,
    field_name: str,
    *,
    minimum: Decimal,
    maximum: Decimal,
) -> Decimal:
    try:
        candidate = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} 必须是数字") from exc
    if candidate < minimum or candidate > maximum:
        raise ValueError(f"{field_name} 必须在 {minimum} 到 {maximum} 之间")
    return candidate


def _int_between(value: object, field_name: str, *, minimum: int, maximum: int) -> int:
    try:
        candidate = int(str(value))
    except ValueError as exc:
        raise ValueError(f"{field_name} 必须是整数") from exc
    if candidate < minimum or candidate > maximum:
        raise ValueError(f"{field_name} 必须在 {minimum} 到 {maximum} 之间")
    return candidate


def _float_text(value: float) -> str:
    return f"{value:.2f}"


def _variant_id(param: str, value: object) -> str:
    normalized_value = str(value).replace(".", "").replace("-", "neg").replace("_", "-")
    normalized_param = param.replace(".", "-").replace("_", "-")
    return f"llm-{normalized_param}-{normalized_value}"


def _candidate_value_for_id(overrides: Mapping[str, object]) -> object:
    if "signal" in overrides:
        signal = cast(Mapping[str, object], overrides["signal"])
        if "min_score" in signal:
            return signal["min_score"]
        weights = signal.get("weights")
        if isinstance(weights, Mapping):
            weight_values = cast(Mapping[str, object], weights)
            for key in ("technical", "market"):
                if key in weight_values:
                    return weight_values[key]
    if "risk" in overrides:
        risk = cast(Mapping[str, object], overrides["risk"])
        for key in (
            "stop_loss_pct",
            "min_holding_trade_days",
            "max_holding_trade_days",
            "max_positions",
        ):
            if key in risk:
                return risk[key]
    return "unknown"


def _deep_merge(base: dict[str, object], overrides: Mapping[str, object]) -> dict[str, object]:
    result = deepcopy(base)
    for key, value in overrides.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _deep_merge(
                cast(dict[str, object], result[key]),
                cast(Mapping[str, object], value),
            )
        else:
            result[key] = cast(object, value)
    return result


def _mapping_list(value: object) -> list[Mapping[str, object]]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [cast(Mapping[str, object], item) for item in values if isinstance(item, Mapping)]


def _float(value: object) -> float:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _int(value: object) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return 0


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    values = cast(list[object], value)
    return [str(item) for item in values]


def _dict_mappings(values: list[dict[str, Any]]) -> list[Mapping[str, object]]:
    return [cast(Mapping[str, object], value) for value in values]


def _table_cell(payload: Mapping[str, object], field_name: str) -> object:
    value = payload.get(field_name)
    return "" if value is None else value


def _window_from_evaluation_id(evaluation_id: str) -> int:
    suffix = evaluation_id.rsplit("-", maxsplit=1)[-1]
    if suffix.endswith("d"):
        try:
            return int(suffix[:-1])
        except ValueError:
            return 0
    return 0
