"""Compare Phase 1.6 stacks on BTC/ETH 4H with fees enabled."""

from __future__ import annotations

from pathlib import Path

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def main() -> None:
    files = [Path("data/btcusdt_4h.csv"), Path("data/ethusdt_4h.csv")]
    bt = BacktestConfig(initial_equity=10_000.0, risk_per_trade=0.01, fee_bps=4.0)

    configs: list[tuple[str, StrategyConfig]] = [
        ("baseline", StrategyConfig()),
        ("htf", StrategyConfig(require_htf_bias=True)),
        (
            "best(htf+lon_ny)",
            StrategyConfig(require_htf_bias=True, require_session=True, session_mode="london_ny"),
        ),
        (
            "best+crt_reclaim",
            StrategyConfig(
                require_htf_bias=True,
                require_session=True,
                session_mode="london_ny",
                require_crt_reclaim=True,
            ),
        ),
        (
            "best+crt_sweep",
            StrategyConfig(
                require_htf_bias=True,
                require_session=True,
                session_mode="london_ny",
                require_crt_sweep=True,
            ),
        ),
        (
            "best+crt_both",
            StrategyConfig(
                require_htf_bias=True,
                require_session=True,
                session_mode="london_ny",
                require_crt_reclaim=True,
                require_crt_sweep=True,
            ),
        ),
    ]

    for path in files:
        if not path.exists():
            print(f"SKIP missing {path}")
            continue
        ohlcv = load_ohlcv(path)
        print(f"\n=== {path.name} | bars={len(ohlcv)} | fee_bps=4 ===")
        print(
            f"{'config':<20} {'n':>4} {'win%':>6} {'pnl':>9} {'mdd%':>6} {'pf':>7} {'equity':>9}"
        )
        best_name = ""
        best_pnl = float("-inf")
        for name, cfg in configs:
            m = Backtester(cfg, bt).run(ohlcv).metrics
            pf = m["profit_factor"]
            pfs = "inf" if pf == float("inf") else f"{pf:.3f}"
            print(
                f"{name:<20} {int(m['n_trades']):>4} {m['win_rate']*100:>5.1f}% "
                f"{m['total_pnl']:>9.2f} {m['max_drawdown']*100:>5.2f} {pfs:>7} "
                f"{m['final_equity']:>9.2f}"
            )
            if m["total_pnl"] > best_pnl:
                best_pnl = m["total_pnl"]
                best_name = name
        print(f"Best: {best_name} ({best_pnl:.2f})")


if __name__ == "__main__":
    main()
