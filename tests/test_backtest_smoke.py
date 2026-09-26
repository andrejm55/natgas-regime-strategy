from __future__ import annotations

from natgas_regime.workflow import run_backtest_from_config


def test_sample_backtest_runs() -> None:
    backtest, metrics = run_backtest_from_config("config/natgas_outright.yaml")
    assert not backtest.empty
    assert "equity" in backtest.columns
    assert metrics["end_equity"] > 0
