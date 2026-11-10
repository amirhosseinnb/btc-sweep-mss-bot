"""Baseline vs HTF-bias across available crypto CSVs."""

from __future__ import annotations

from pathlib import Path

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def main() -> None:
    bt = BacktestConfig(initial_equity=10_000.0, risk_per_trade=0.01)
    cfgs = {
        "baseline": StrategyConfig(),
        "htf": StrategyConfig(require_htf_bias=True, htf_rule="1D"),
    }
    files = [
        Path("data/btcusdt_1h.csv"),
        Path("data/btcusdt_4h.csv"),
        Path("data/ethusdt_1h.csv"),
        Path("data/btcusdt_15m.csv"),
    ]
    print(f"{'file':<22} {'cfg':<8} {'n':>4} {'win%':>6} {'pnl':>9} {'pf':>7} {'mdd%':>6}")
    for path in files:
        df = load_ohlcv(path)
        for name, cfg in cfgs.items():
            m = Backtester(cfg, bt).run(df).metrics
            pf = m["profit_factor"]
            pfs = "inf" if pf == float("inf") else f"{pf:.3f}"
            print(
                f"{path.name:<22} {name:<8} {int(m['n_trades']):>4} "
                f"{m['win_rate'] * 100:>5.1f}% {m['total_pnl']:>9.2f} "
                f"{pfs:>7} {m['max_drawdown'] * 100:>5.2f}"
            )


if __name__ == "__main__":
    main()
