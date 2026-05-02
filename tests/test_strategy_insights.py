from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from ashare_agent.agents.strategy_params_agent import StrategyParamsAgent
from ashare_agent.domain import AgentResult
from ashare_agent.llm.mock import MockLLMClient
from ashare_agent.providers.mock import MockProvider
from ashare_agent.repository import InMemoryRepository
from ashare_agent.strategy_insights import (
    HypothesisVariantBuilder,
    StrategyInsightAgent,
    StrategyInsightRunner,
)


def _write_base_params(path: Path) -> None:
    path.write_text(
        """
version: "strategy-params-v1"
risk:
  max_positions: 5
  target_position_pct: "0.10"
  min_cash: "100"
  max_daily_loss_pct: "0.02"
  stop_loss_pct: "0.05"
  price_limit_pct: "0.098"
  min_holding_trade_days: 2
  max_holding_trade_days: 10
  blacklist: []
paper_trader:
  initial_cash: "100000"
  position_size_pct: "0.10"
  slippage_pct: "0.001"
signal:
  min_score: "0.55"
  max_daily_signals: 1
  weights:
    technical: "0.45"
    market: "0.25"
    event: "0.20"
    risk_penalty: "0.10"
""",
        encoding="utf-8",
    )


class JsonInsightLLM:
    def __init__(self, payload: dict[str, Any] | str) -> None:
        self.payload = payload

    def generate_strategy_insight(
        self,
        trade_date: date,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        content = self.payload if isinstance(self.payload, str) else json.dumps(self.payload)
        return {"model": "json-llm", "content": content, "raw_response": {"context": context}}


def _valid_llm_payload() -> dict[str, Any]:
    return {
        "summary": "今日有信号但被已有持仓规则拒绝。",
        "attribution": ["信号数量偏少", "数据质量正常"],
        "hypotheses": [
            {
                "area": "signal.min_score",
                "direction": "lower",
                "reason": "近期信号偏少",
                "risk": "可能增加低质量交易",
            }
        ],
        "recommended_experiments": [
            {
                "name": "降低最低评分阈值",
                "param": "signal.min_score",
                "candidate_value": 0.50,
            },
            {
                "name": "错误地关闭止损",
                "param": "risk.stop_loss_pct",
                "candidate_value": 0,
            },
            {
                "name": "超过白名单",
                "param": "paper_trader.position_size_pct",
                "candidate_value": 0.25,
            },
            {
                "name": "沿用用户语义里的最大持仓",
                "param": "paper_trader.max_positions",
                "candidate_value": 4,
            },
        ],
    }


def test_strategy_insight_agent_parses_structured_llm_json() -> None:
    insight = StrategyInsightAgent(JsonInsightLLM(_valid_llm_payload())).generate(
        trade_date=date(2026, 4, 30),
        context={"day_summary": {"trade_date": "2026-04-30"}},
    )

    assert insight.model == "json-llm"
    assert insight.summary == "今日有信号但被已有持仓规则拒绝。"
    assert insight.hypotheses[0]["area"] == "signal.min_score"
    assert insight.recommended_experiments[0]["candidate_value"] == 0.50


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ("not-json", "strategy insight JSON"),
        ({"summary": "bad"}, "hypotheses"),
    ],
)
def test_strategy_insight_agent_rejects_bad_llm_json(
    payload: dict[str, Any] | str,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        StrategyInsightAgent(JsonInsightLLM(payload)).generate(
            trade_date=date(2026, 4, 30),
            context={},
        )


def test_hypothesis_variant_builder_compiles_whitelisted_variants(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_base_params(config_path)
    params = StrategyParamsAgent(config_path).load()
    insight = StrategyInsightAgent(JsonInsightLLM(_valid_llm_payload())).generate(
        trade_date=date(2026, 4, 30),
        context={},
    )

    result = HypothesisVariantBuilder(params).build(insight)

    assert [variant.id for variant in result.variants] == [
        "baseline",
        "llm-signal-min-score-050",
        "llm-risk-max-positions-4",
    ]
    assert result.variants[1].overrides == {"signal": {"min_score": "0.50"}}
    assert result.variants[2].overrides == {"risk": {"max_positions": 4}}
    rejected = {item["param"]: item["policy_status"] for item in result.experiments}
    assert rejected["risk.stop_loss_pct"] == "rejected_by_policy"
    assert rejected["paper_trader.position_size_pct"] == "rejected_by_policy"


def test_strategy_insight_runner_runs_twenty_forty_sixty_day_evaluations(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_base_params(config_path)
    params = StrategyParamsAgent(config_path).load()
    repository = InMemoryRepository()
    created_windows: list[int] = []

    class FakeEvaluationRunner:
        def __init__(self, *, strategy_config: Any, **_: Any) -> None:
            self.strategy_config = strategy_config
            created_windows.append(strategy_config.default_window_trade_days)

        def run(
            self,
            *,
            evaluation_id: str | None = None,
            start_date: date | None = None,
            end_date: date | None = None,
        ) -> AgentResult:
            resolved_id = evaluation_id or "fake-evaluation"
            window = self.strategy_config.default_window_trade_days
            return AgentResult(
                name="strategy_evaluation",
                success=True,
                payload={
                    "evaluation_id": resolved_id,
                    "provider": "mock",
                    "start_date": "2026-01-01",
                    "end_date": "2026-04-30",
                    "variant_count": 2,
                    "report_path": f"reports/{resolved_id}/strategy-evaluation.md",
                    "recommendation": {
                        "summary": "fake",
                        "recommended_variant_ids": ["llm-signal-min-score-050"],
                    },
                    "variants": [
                        {
                            "id": "baseline",
                            "label": "当前参数",
                            "version": "strategy-params-v1-baseline",
                            "backtest_id": f"{resolved_id}-baseline",
                            "success": True,
                            "attempted_days": window,
                            "succeeded_days": window,
                            "failed_days": 0,
                            "source_failure_rate": 0.0,
                            "data_quality_failure_rate": 0.0,
                            "signal_count": 2,
                            "risk_approved_count": 1,
                            "risk_rejected_count": 1,
                            "order_count": 1,
                            "execution_failed_count": 0,
                            "closed_trade_count": 1,
                            "signal_hit_count": 1,
                            "signal_hit_rate": 1.0,
                            "open_position_count": 0,
                            "holding_pnl": "10",
                            "total_return": 0.01,
                            "max_drawdown": 0.03,
                        },
                        {
                            "id": "llm-signal-min-score-050",
                            "label": "降低最低评分阈值",
                            "version": "strategy-params-v1-llm-signal-min-score-050",
                            "backtest_id": f"{resolved_id}-candidate",
                            "success": True,
                            "attempted_days": window,
                            "succeeded_days": window,
                            "failed_days": 0,
                            "source_failure_rate": 0.0,
                            "data_quality_failure_rate": 0.0,
                            "signal_count": 3,
                            "risk_approved_count": 2,
                            "risk_rejected_count": 1,
                            "order_count": 2,
                            "execution_failed_count": 0,
                            "closed_trade_count": 1,
                            "signal_hit_count": 1,
                            "signal_hit_rate": 1.0,
                            "open_position_count": 1,
                            "holding_pnl": "20",
                            "total_return": 0.02,
                            "max_drawdown": 0.02,
                        },
                    ],
                },
            )

    runner = StrategyInsightRunner(
        provider=MockProvider(),
        llm_client=JsonInsightLLM(_valid_llm_payload()),
        report_root=tmp_path / "reports",
        repository=repository,
        strategy_params=params,
        provider_name="mock",
        required_data_sources=set(),
        evaluation_runner_class=FakeEvaluationRunner,
    )

    result = runner.run(trade_date=date(2026, 4, 30), insight_id="insight-smoke")

    assert result.success is True
    assert created_windows == [20, 40, 60]
    assert result.payload["insight_id"] == "insight-smoke"
    assert result.payload["manual_status"] == "pending_review"
    assert result.payload["evaluation_windows"][0]["evaluation_id"] == "insight-smoke-20d"
    assert result.payload["gate_summary"]["recommended_variant_ids"] == [
        "llm-signal-min-score-050"
    ]
    assert repository.records_for("pipeline_runs")[-1]["payload"]["stage"] == "strategy_insight"
    assert repository.records[-1]["artifact_type"] == "strategy_insight"
    assert (tmp_path / "reports" / "insight-smoke" / "strategy-insights.md").exists()


def test_mock_llm_generates_deterministic_strategy_insight_json() -> None:
    response = MockLLMClient().generate_strategy_insight(
        date(2026, 4, 30),
        {"day_summary": {"signals": []}},
    )

    parsed = json.loads(str(response["content"]))
    assert parsed["summary"]
    assert parsed["hypotheses"][0]["area"] == "signal.min_score"
