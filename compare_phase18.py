"""Compare risk guards + relaxed FVG on BTC 4H."""

from __future__ import annotations

from pathlib import Path

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def main() -> None:
    ohlcv = load_ohlcv(Path("data/btcusdt_4h.csv"))
    base = dict(require_htf_bias=True, require_session=True, session_mode="london_ny")
    rows = [
        (
            "best_mss+guards",
            StrategyConfig(**base),
            BacktestConfig(fee_bps=4.0, enable_risk_guards=True),
        ),
        (
            "best_mss-noguard",
            StrategyConfig(**base),
            BacktestConfig(fee_bps=4.0, enable_risk_guards=False),
        ),
        (
            "best_fvg+guards",
            StrategyConfig(**base, entry_mode="fvg_retrace"),
            BacktestConfig(fee_bps=4.0, enable_risk_guards=True),
        ),
    ]
    print(f"{'cfg':<18} {'n':>4} {'win%':>6} {'pnl':>9} {'mdd%':>6} {'skip':>5} {'pf':>7}")
    for name, sc, bc in rows:
        m = Backtester(sc, bc).run(ohlcv).metrics
        pf = m["profit_factor"]
        pfs = "inf" if pf == float("inf") else f"{pf:.3f}"
        print(
            f"{name:<18} {int(m['n_trades']):>4} {m['win_rate']*100:>5.1f}% "
            f"{m['total_pnl']:>9.2f} {m['max_drawdown']*100:>5.2f} "
            f"{int(m.get('skipped_by_risk', 0)):>5} {pfs:>7}"
        )


if __name__ == "__main__":
    main()
