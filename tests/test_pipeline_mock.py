from __future__ import annotations

from datetime import date
from pathlib import Path

from ashare_agent.pipeline import build_mock_pipeline


def test_mock_pipeline_runs_pre_market_and_post_market_with_audit_outputs(tmp_path: Path) -> None:
    pipeline = build_mock_pipeline(report_root=tmp_path)
    trade_date = date(2026, 4, 29)

    pre_market = pipeline.run_pre_market(trade_date)
    intraday = pipeline.run_intraday_watch(trade_date)
    review = pipeline.run_post_market_review(trade_date)

    assert pre_market.success is True
    assert intraday.success is True
    assert review.success is True
    assert len(pre_market.payload["signals"]) <= 1
    assert "paper" in review.payload["report_path"]
    assert (tmp_path / "2026-04-29" / "pre-market.md").exists()
    assert (tmp_path / "2026-04-29" / "post-market-review.md").exists()
