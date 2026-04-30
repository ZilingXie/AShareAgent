from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from ashare_agent.agents.strategy_params_agent import StrategyParamsAgent


def _write_config(path: Path, *, extra: str = "") -> None:
    path.write_text(
        f"""
version: "test-params-v1"
risk:
  max_positions: 3
  target_position_pct: "0.15"
  min_cash: "500"
  max_daily_loss_pct: "0.03"
  stop_loss_pct: "0.07"
  price_limit_pct: "0.088"
  min_holding_trade_days: 1
  max_holding_trade_days: 4
  blacklist:
    - "600000"
paper_trader:
  initial_cash: "200000"
  position_size_pct: "0.15"
  slippage_pct: "0.002"
signal:
  min_score: "0.60"
  max_daily_signals: 2
  weights:
    technical: "0.50"
    market: "0.20"
    event: "0.20"
    risk_penalty: "0.10"
{extra}
""",
        encoding="utf-8",
    )


def test_strategy_params_agent_loads_version_and_snapshot(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)

    params = StrategyParamsAgent(config_path).load()

    assert params.version == "test-params-v1"
    assert params.risk.stop_loss_pct == Decimal("0.07")
    assert params.signal.min_score == 0.60
    assert params.signal.max_daily_signals == 2
    assert params.signal.weights.technical == 0.50
    assert params.risk.blacklist == {"600000"}
    assert params.snapshot() == {
        "version": "test-params-v1",
        "risk": {
            "max_positions": 3,
            "target_position_pct": "0.15",
            "min_cash": "500",
            "max_daily_loss_pct": "0.03",
            "stop_loss_pct": "0.07",
            "price_limit_pct": "0.088",
            "min_holding_trade_days": 1,
            "max_holding_trade_days": 4,
            "blacklist": ["600000"],
        },
        "paper_trader": {
            "initial_cash": "200000",
            "position_size_pct": "0.15",
            "slippage_pct": "0.002",
        },
        "signal": {
            "min_score": 0.6,
            "max_daily_signals": 2,
            "weights": {
                "technical": 0.5,
                "market": 0.2,
                "event": 0.2,
                "risk_penalty": 0.1,
            },
        },
    }


def test_strategy_params_agent_rejects_missing_required_field(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    config_path.write_text(
        """
version: "broken"
risk:
  max_positions: 3
paper_trader:
  initial_cash: "200000"
  position_size_pct: "0.15"
  slippage_pct: "0.002"
signal:
  min_score: "0.60"
  max_daily_signals: 2
  weights:
    technical: "0.50"
    market: "0.20"
    event: "0.20"
    risk_penalty: "0.10"
""",
        encoding="utf-8",
    )

    try:
        StrategyParamsAgent(config_path).load()
    except ValueError as exc:
        assert "策略参数配置缺少 risk." in str(exc)
    else:
        raise AssertionError("缺少必需策略参数字段必须显式失败")


def test_strategy_params_agent_rejects_invalid_percentage(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace('stop_loss_pct: "0.07"', 'stop_loss_pct: "1.50"'),
        encoding="utf-8",
    )

    try:
        StrategyParamsAgent(config_path).load()
    except ValueError as exc:
        assert "risk.stop_loss_pct" in str(exc)
    else:
        raise AssertionError("非法百分比必须显式失败")


def test_strategy_params_agent_rejects_invalid_holding_range(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("max_holding_trade_days: 4", "max_holding_trade_days: 0"),
        encoding="utf-8",
    )

    try:
        StrategyParamsAgent(config_path).load()
    except ValueError as exc:
        assert "max_holding_trade_days" in str(exc)
    else:
        raise AssertionError("最多持有期小于最少持有期必须显式失败")


def test_strategy_params_agent_rejects_missing_signal_section(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8").split("signal:")[0]
    config_path.write_text(text, encoding="utf-8")

    with pytest.raises(ValueError, match="signal"):
        StrategyParamsAgent(config_path).load()


def test_strategy_params_agent_rejects_invalid_signal_weight(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace('technical: "0.50"', 'technical: "1.50"'),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="signal.weights.technical"):
        StrategyParamsAgent(config_path).load()


def test_strategy_params_agent_rejects_invalid_max_daily_signals(tmp_path: Path) -> None:
    config_path = tmp_path / "strategy_params.yml"
    _write_config(config_path)
    text = config_path.read_text(encoding="utf-8")
    config_path.write_text(
        text.replace("max_daily_signals: 2", "max_daily_signals: 0"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="signal.max_daily_signals"):
        StrategyParamsAgent(config_path).load()
