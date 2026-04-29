from __future__ import annotations

import pkgutil
from pathlib import Path

import ashare_agent


def test_package_does_not_ship_real_broker_or_real_order_modules() -> None:
    module_names = {
        module.name for module in pkgutil.walk_packages(ashare_agent.__path__, "ashare_agent.")
    }

    forbidden_fragments = {"broker", "real_order", "live_trading"}

    assert not any(fragment in name for fragment in forbidden_fragments for name in module_names)


def test_env_file_is_ignored() -> None:
    gitignore = Path(".gitignore").read_text(encoding="utf-8")

    assert ".env" in gitignore
