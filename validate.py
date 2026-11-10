"""
Phase 1.9 validation: multi-asset + walk-forward OOS on the fixed `best` preset.

No parameter fitting in-sample — folds only measure stability of the same rules.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def best_strategy_config() -> StrategyConfig:
    return StrategyConfig(
        require_htf_bias=True,
        require_session=True,
        session_mode="london_ny",
        entry_mode="mss_close",
    )


def best_backtest_config(equity: float = 10_000.0) -> BacktestConfig:
    return BacktestConfig(
        initial_equity=equity,
        risk_per_trade=0.01,
        fee_bps=4.0,
        slippage_bps=2.0,
        spread_bps=2.0,
        daily_loss_limit=0.03,
        max_consecutive_losses=3,
        enable_risk_guards=True,
    )


def run_full(df: pd.DataFrame) -> dict[str, float]:
    return Backtester(best_strategy_config(), best_backtest_config()).run(df).metrics


def walk_forward_folds(
    df: pd.DataFrame,
    *,
    oos_days: int = 90,
    step_days: int = 90,
    min_bars: int = 200,
) -> pd.DataFrame:
    """
    Rolling OOS windows on New York timestamps.

    Each fold evaluates only the OOS slice with a fresh equity account.
    """
    if df.empty:
        return pd.DataFrame()

    start = df.index.min()
    end = df.index.max()
    rows: list[dict] = []
    cursor = start

    while True:
        oos_start = cursor
        oos_end = oos_start + pd.Timedelta(days=oos_days)
        if oos_start >= end:
            break
        if oos_end > end:
            oos_end = end

        slice_df = df[(df.index >= oos_start) & (df.index < oos_end)]
        if len(slice_df) >= min_bars:
            m = run_full(slice_df)
            rows.append(
                {
                    "oos_start": oos_start,
                    "oos_end": oos_end,
                    "bars": len(slice_df),
                    "trades": int(m["n_trades"]),
                    "win_rate": m["win_rate"],
                    "total_pnl": m["total_pnl"],
                    "max_drawdown": m["max_drawdown"],
                    "profit_factor": m["profit_factor"],
                    "final_equity": m["final_equity"],
                }
            )

        next_cursor = cursor + pd.Timedelta(days=step_days)
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if cursor >= end:
            break

    return pd.DataFrame(rows)


def summarize_folds(folds: pd.DataFrame) -> dict[str, float]:
    if folds.empty:
        return {
            "folds": 0.0,
            "positive_folds": 0.0,
            "mean_pnl": 0.0,
            "median_pnl": 0.0,
            "mean_pf": 0.0,
            "mean_mdd": 0.0,
            "total_trades": 0.0,
        }
    pf = folds["profit_factor"].replace([np.inf, -np.inf], np.nan)
    return {
        "folds": float(len(folds)),
        "positive_folds": float((folds["total_pnl"] > 0).sum()),
        "mean_pnl": float(folds["total_pnl"].mean()),
        "median_pnl": float(folds["total_pnl"].median()),
        "mean_pf": float(pf.mean(skipna=True)) if pf.notna().any() else 0.0,
        "mean_mdd": float(folds["max_drawdown"].mean()),
        "total_trades": float(folds["trades"].sum()),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Multi-asset + walk-forward validation")
    p.add_argument(
        "--files",
        nargs="+",
        type=Path,
        default=[
            Path("data/btcusdt_4h.csv"),
            Path("data/ethusdt_4h.csv"),
            Path("data/solusdt_4h.csv"),
        ],
    )
    p.add_argument("--oos-days", type=int, default=90)
    p.add_argument("--step-days", type=int, default=90)
    p.add_argument(
        "--out-dir",
        type=Path,
        default=Path("data/validation"),
        help="Directory for fold CSVs",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print(" Validation — preset=best | fee=4bps | slip=2bps | spread=2bps | risk ON")
    print("=" * 72)

    print("\n--- Full-sample multi-asset ---")
    print(
        f"{'file':<22} {'bars':>5} {'n':>4} {'win%':>6} {'pnl':>9} {'mdd%':>6} {'pf':>7}"
    )
    full_rows: list[dict] = []
    for path in args.files:
        if not path.exists():
            print(f"{path.name:<22} MISSING")
            continue
        df = load_ohlcv(path)
        m = run_full(df)
        pf = m["profit_factor"]
        pfs = "inf" if pf == float("inf") else f"{pf:.3f}"
        print(
            f"{path.name:<22} {len(df):>5} {int(m['n_trades']):>4} "
            f"{m['win_rate']*100:>5.1f}% {m['total_pnl']:>9.2f} "
            f"{m['max_drawdown']*100:>5.2f} {pfs:>7}"
        )
        full_rows.append({"file": path.name, **m, "bars": len(df)})

    print("\n--- Walk-forward OOS folds ---")
    print(
        f"{'file':<22} {'folds':>5} {'pos':>4} {'meanPnL':>9} {'medPnL':>9} "
        f"{'meanPF':>7} {'meanMDD':>7} {'trades':>6}"
    )
    for path in args.files:
        if not path.exists():
            continue
        df = load_ohlcv(path)
        folds = walk_forward_folds(
            df,
            oos_days=args.oos_days,
            step_days=args.step_days,
        )
        out = args.out_dir / f"wf_{path.stem}.csv"
        folds.to_csv(out, index=False)
        s = summarize_folds(folds)
        print(
            f"{path.name:<22} {int(s['folds']):>5} {int(s['positive_folds']):>4} "
            f"{s['mean_pnl']:>9.2f} {s['median_pnl']:>9.2f} "
            f"{s['mean_pf']:>7.3f} {s['mean_mdd']*100:>6.2f}% {int(s['total_trades']):>6}"
        )
        print(f"  folds -> {out}")

        if not folds.empty:
            for _, r in folds.iterrows():
                pf = r["profit_factor"]
                pfs = "inf" if pf == float("inf") else f"{pf:.2f}"
                print(
                    f"    {r['oos_start'].date()} -> {r['oos_end'].date()} | "
                    f"n={int(r['trades']):>2} pnl={r['total_pnl']:>8.2f} "
                    f"wr={r['win_rate']*100:>5.1f}% pf={pfs}"
                )

    if full_rows:
        pd.DataFrame(full_rows).to_csv(args.out_dir / "full_sample.csv", index=False)
        print(f"\nFull-sample summary -> {args.out_dir / 'full_sample.csv'}")
    print("=" * 72)


if __name__ == "__main__":
    main()
