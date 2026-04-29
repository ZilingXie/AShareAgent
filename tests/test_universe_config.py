from __future__ import annotations

from pathlib import Path

from ashare_agent.config import load_universe


def test_load_universe_from_yaml_config(tmp_path: Path) -> None:
    config_path = tmp_path / "universe.yml"
    config_path.write_text(
        """
assets:
  - symbol: "510300"
    name: "沪深300ETF"
    asset_type: "ETF"
  - symbol: "600000"
    name: "浦发银行"
    asset_type: "STOCK"
    enabled: false
""",
        encoding="utf-8",
    )

    assets = load_universe(config_path)

    assert [asset.symbol for asset in assets] == ["510300", "600000"]
    assert assets[0].asset_type == "ETF"
    assert assets[1].enabled is False

