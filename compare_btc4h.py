"""Compare Phase-1.5 filter combinations on BTCUSDT 4H."""

from __future__ import annotations

from pathlib import Path

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def main() -> None:
    path = Path("data/btcusdt_4h.csv")
    ohlcv = load_ohlcv(path)
    bt_cfg = BacktestConfig(initial_equity=10_000.0, risk_per_trade=0.01)

    configs: list[tuple[str, StrategyConfig]] = [
        ("baseline", StrategyConfig()),
        ("disp", StrategyConfig(require_displacement=True)),
        ("htf", StrategyConfig(require_htf_bias=True, htf_rule="1D")),
        (
            "disp+htf",
            StrategyConfig(require_displacement=True, require_htf_bias=True, htf_rule="1D"),
        ),
        (
            "disp+htf+max12",
            StrategyConfig(
                require_displacement=True,
                require_htf_bias=True,
                htf_rule="1D",
                max_bars_sweep_to_mss=12,
            ),
        ),
        (
            "disp+htf+sweep0.15",
            StrategyConfig(
                require_displacement=True,
                require_htf_bias=True,
                htf_rule="1D",
                max_bars_sweep_to_mss=12,
                min_sweep_atr_mult=0.15,
            ),
        ),
        (
            "retrace+disp+htf",
            StrategyConfig(
                entry_mode="first_retracement",
                require_displacement=True,
                require_htf_bias=True,
                htf_rule="1D",
                max_bars_sweep_to_mss=12,
            ),
        ),
        (
            "htf+london_ny",
            StrategyConfig(
                require_htf_bias=True,
                htf_rule="1D",
                require_session=True,
                session_mode="london_ny",
            ),
        ),
        (
            "htf+killzones",
            StrategyConfig(
                require_htf_bias=True,
                htf_rule="1D",
                require_session=True,
                session_mode="killzones",
            ),
        ),
        (
            "htf+london",
            StrategyConfig(
                require_htf_bias=True,
                htf_rule="1D",
                require_session=True,
                session_mode="london",
            ),
        ),
        (
            "htf+newyork",
            StrategyConfig(
                require_htf_bias=True,
                htf_rule="1D",
                require_session=True,
                session_mode="newyork",
            ),
        ),
    ]

    print(f"Dataset: {path} | bars={len(ohlcv)}")
    print(
        f"{'config':<22} {'trades':>6} {'win%':>7} {'pnl':>10} {'mdd%':>7} {'pf':>8} {'equity':>10}"
    )
    print("-" * 78)

    best_name = ""
    best_pnl = float("-inf")
    for name, cfg in configs:
        result = Backtester(cfg, bt_cfg).run(ohlcv)
        m = result.metrics
        pf = m["profit_factor"]
        pf_str = "inf" if pf == float("inf") else f"{pf:.3f}"
        print(
            f"{name:<22} {int(m['n_trades']):>6} {m['win_rate']*100:>6.1f}% "
            f"{m['total_pnl']:>10.2f} {m['max_drawdown']*100:>6.2f}% "
            f"{pf_str:>8} {m['final_equity']:>10.2f}"
        )
        if m["total_pnl"] > best_pnl:
            best_pnl = m["total_pnl"]
            best_name = name

    print("-" * 78)
    print(f"Best PnL config: {best_name} ({best_pnl:.2f})")


if __name__ == "__main__":
    main()
