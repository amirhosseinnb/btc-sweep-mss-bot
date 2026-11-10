"""Compare Phase 1.7 FVG entry + divergence stacks."""

from __future__ import annotations

from pathlib import Path

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def main() -> None:
    files = [Path("data/btcusdt_4h.csv"), Path("data/ethusdt_4h.csv")]
    bt = BacktestConfig(initial_equity=10_000.0, risk_per_trade=0.01, fee_bps=4.0)
    base = dict(require_htf_bias=True, require_session=True, session_mode="london_ny")

    configs: list[tuple[str, StrategyConfig]] = [
        ("best_mss", StrategyConfig(**base, entry_mode="mss_close")),
        ("best_fvg", StrategyConfig(**base, entry_mode="fvg_retrace")),
        ("best_mss+div", StrategyConfig(**base, entry_mode="mss_close", require_divergence=True)),
        ("best_fvg+div", StrategyConfig(**base, entry_mode="fvg_retrace", require_divergence=True)),
        (
            "best_fvg+crt",
            StrategyConfig(
                **base,
                entry_mode="fvg_retrace",
                require_crt_reclaim=True,
                require_crt_sweep=True,
            ),
        ),
    ]

    for path in files:
        if not path.exists():
            print(f"SKIP {path}")
            continue
        ohlcv = load_ohlcv(path)
        print(f"\n=== {path.name} | bars={len(ohlcv)} | fee=4bps ===")
        print(f"{'config':<16} {'n':>4} {'win%':>6} {'pnl':>9} {'mdd%':>6} {'pf':>7}")
        best_name, best_pnl = "", float("-inf")
        for name, cfg in configs:
            m = Backtester(cfg, bt).run(ohlcv).metrics
            pf = m["profit_factor"]
            pfs = "inf" if pf == float("inf") else f"{pf:.3f}"
            print(
                f"{name:<16} {int(m['n_trades']):>4} {m['win_rate']*100:>5.1f}% "
                f"{m['total_pnl']:>9.2f} {m['max_drawdown']*100:>5.2f} {pfs:>7}"
            )
            if m["total_pnl"] > best_pnl:
                best_pnl = m["total_pnl"]
                best_name = name
        print(f"Best: {best_name} ({best_pnl:.2f})")


if __name__ == "__main__":
    main()
