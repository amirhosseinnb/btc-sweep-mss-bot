"""
Phase 1 MVP entrypoint: load OHLCV CSV, run the offline backtest, print metrics.

Usage:
    python run.py
    python run.py --csv data/sample_ohlcv.csv --equity 10000 --rr 2.0
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from backtester import BacktestConfig, Backtester
from core_strategy import DEFAULT_TIMEZONE, StrategyConfig, to_project_timezone
from philosophy import check_philosophy
from trade_management import TradeManageConfig


def load_ohlcv(path: Path, timezone: str = DEFAULT_TIMEZONE) -> pd.DataFrame:
    df = pd.read_csv(path)
    cols = {c.lower(): c for c in df.columns}
    rename = {}
    for need in ("open", "high", "low", "close", "volume"):
        if need in cols:
            rename[cols[need]] = need
    df = df.rename(columns=rename)

    time_col = None
    for candidate in ("timestamp", "datetime", "date", "time"):
        if candidate in {c.lower() for c in df.columns}:
            time_col = next(c for c in df.columns if c.lower() == candidate)
            break
    if time_col is None:
        raise ValueError("CSV must include a timestamp/date column")

    # Exchange CSVs are UTC; convert everything to New York project time.
    df[time_col] = pd.to_datetime(df[time_col], utc=True)
    df = df.set_index(time_col).sort_index()
    df.index = to_project_timezone(df.index, timezone=timezone)
    required = ["open", "high", "low", "close"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")
    return df


def make_sample_ohlcv(n_bars: int = 800, seed: int = 42) -> pd.DataFrame:
    """Synthetic trending + mean-reverting OHLCV for local smoke tests."""
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2024-01-01", periods=n_bars, freq="h")
    # Piecewise drift creates swing structure that the rules can latch onto.
    drift = np.zeros(n_bars)
    drift[100:220] = 0.08
    drift[220:320] = -0.10
    drift[320:480] = 0.06
    drift[480:600] = -0.07
    drift[600:] = 0.04
    noise = rng.normal(0.0, 0.35, size=n_bars)
    log_close = np.cumsum(drift + noise)
    close = 100 * np.exp((log_close - log_close[0]) / 100.0)
    open_ = np.roll(close, 1)
    open_[0] = close[0]
    spread = np.abs(rng.normal(0.25, 0.15, size=n_bars))
    high = np.maximum(open_, close) + spread
    low = np.minimum(open_, close) - spread
    # Inject a few explicit sweep wicks.
    for i in (150, 260, 390, 520, 670):
        if i < n_bars:
            if drift[i] >= 0:
                low[i] = low[i] - 1.2
            else:
                high[i] = high[i] + 1.2
    volume = rng.integers(1_000, 5_000, size=n_bars)
    return pd.DataFrame(
        {"open": open_, "high": high, "low": low, "close": close, "volume": volume},
        index=idx,
    )


def ensure_sample_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        sample = make_sample_ohlcv()
        out = sample.reset_index().rename(columns={"index": "timestamp"})
        out.to_csv(path, index=False)
        print(f"Wrote sample dataset -> {path}")
    return path


def format_metrics(metrics: dict[str, float]) -> str:
    wr = metrics["win_rate"] * 100.0
    mdd = metrics["max_drawdown"] * 100.0
    pf = metrics["profit_factor"]
    pf_str = "inf" if not np.isfinite(pf) else f"{pf:.3f}"
    skipped = int(metrics.get("skipped_by_risk", 0.0))
    skipped_nt = int(metrics.get("skipped_by_no_trade", 0.0))
    partials = int(metrics.get("partial_exits", 0.0))
    return (
        f"Trades         : {int(metrics['n_trades'])}\n"
        f"Win Rate       : {wr:.2f}%\n"
        f"Total PnL      : {metrics['total_pnl']:.2f}\n"
        f"Max Drawdown   : {mdd:.2f}%\n"
        f"Profit Factor  : {pf_str}\n"
        f"Final Equity   : {metrics['final_equity']:.2f}\n"
        f"Skipped(risk)  : {skipped}\n"
        f"Skipped(no-tr) : {skipped_nt}\n"
        f"Partial exits  : {partials}"
    )


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Phase 1 MVP offline SMC backtest")
    p.add_argument(
        "--csv",
        type=Path,
        default=Path("data/sample_ohlcv.csv"),
        help="Path to OHLCV CSV (timestamp, open, high, low, close[, volume])",
    )
    p.add_argument("--equity", type=float, default=10_000.0, help="Initial equity")
    p.add_argument("--risk", type=float, default=0.01, help="Risk fraction per trade")
    p.add_argument("--rr", type=float, default=2.0, help="Take-profit R:R multiple")
    p.add_argument("--swing-n", type=int, default=3, help="Swing left/right window")
    p.add_argument(
        "--entry-mode",
        choices=("mss_close", "first_retracement", "fvg_retrace"),
        default="mss_close",
        help="Entry fill mode (fvg_retrace = pullback into FVG after MSS)",
    )
    p.add_argument(
        "--require-displacement",
        action="store_true",
        help="Require MSS candle body >= 1.5 * ATR(14)",
    )
    p.add_argument(
        "--require-htf-bias",
        action="store_true",
        help="Only take trades aligned with HTF EMA bias",
    )
    p.add_argument("--htf-rule", default="1D", help="HTF resample rule (default 1D)")
    p.add_argument(
        "--max-bars-sweep-mss",
        type=int,
        default=None,
        help="Invalidate setup if MSS takes more than N bars after sweep",
    )
    p.add_argument(
        "--min-sweep-atr",
        type=float,
        default=0.0,
        help="Minimum sweep wick penetration in ATR multiples",
    )
    p.add_argument(
        "--require-session",
        action="store_true",
        help="Only enter during configured New York session windows",
    )
    p.add_argument(
        "--session-mode",
        choices=("london", "newyork", "london_ny", "killzones"),
        default="london_ny",
        help="Session window set (America/New_York local hours)",
    )
    p.add_argument(
        "--require-crt-reclaim",
        action="store_true",
        help="Require close back inside prior NY-day CRT range before MSS entry",
    )
    p.add_argument(
        "--require-crt-sweep",
        action="store_true",
        help="Only keep sweeps that pierce the prior NY-day CRT high/low",
    )
    p.add_argument(
        "--require-divergence",
        action="store_true",
        help="Require recent regular RSI divergence aligned with trade side",
    )
    p.add_argument(
        "--timezone",
        default=DEFAULT_TIMEZONE,
        help=f"Project timezone (default {DEFAULT_TIMEZONE})",
    )
    p.add_argument(
        "--fee-bps",
        type=float,
        default=4.0,
        help="Fee per fill in basis points (default 4.0 ~= 0.04%%)",
    )
    p.add_argument(
        "--slippage-bps",
        type=float,
        default=2.0,
        help="Adverse slippage per fill in bps (default 2)",
    )
    p.add_argument(
        "--spread-bps",
        type=float,
        default=2.0,
        help="Round-trip spread in bps; half applied each side (default 2)",
    )
    p.add_argument(
        "--daily-loss-limit",
        type=float,
        default=0.03,
        help="Halt new entries after daily loss fraction (default 3%%)",
    )
    p.add_argument(
        "--max-consecutive-losses",
        type=int,
        default=3,
        help="Halt new entries after N consecutive losing trades",
    )
    p.add_argument(
        "--no-risk-guards",
        action="store_true",
        help="Disable daily loss / consecutive-loss circuit breakers",
    )
    p.add_argument(
        "--max-trades-per-day",
        type=int,
        default=None,
        help="No-trade: max new entries per NY calendar day",
    )
    p.add_argument(
        "--cooldown-bars-after-loss",
        type=int,
        default=0,
        help="No-trade: bars to wait after a losing trade before next entry",
    )
    p.add_argument(
        "--manage-trades",
        action="store_true",
        help="Enable in-trade management (breakeven / partial / trail)",
    )
    p.add_argument(
        "--be-at-r",
        type=float,
        default=1.0,
        help="Move stop to breakeven after this R multiple (with --manage-trades)",
    )
    p.add_argument(
        "--partial-at-r",
        type=float,
        default=1.0,
        help="Take partial profit at this R multiple (with --manage-trades)",
    )
    p.add_argument(
        "--partial-fraction",
        type=float,
        default=0.5,
        help="Fraction of size to close at partial (default 0.5)",
    )
    p.add_argument(
        "--trail-after-r",
        type=float,
        default=None,
        help="Start trailing stop after this R multiple (optional)",
    )
    p.add_argument(
        "--trail-step-r",
        type=float,
        default=0.5,
        help="Trail distance behind best extreme, in R units",
    )
    p.add_argument(
        "--no-breakeven",
        action="store_true",
        help="Disable breakeven even when --manage-trades is set",
    )
    p.add_argument(
        "--no-partial",
        action="store_true",
        help="Disable partial take-profit even when --manage-trades is set",
    )
    p.add_argument(
        "--enable-scoring",
        action="store_true",
        help="Enable 24-point confluence scoring and min-score filter",
    )
    p.add_argument(
        "--min-score",
        type=int,
        default=12,
        help="Minimum confluence score to take a trade (0-24, default 12)",
    )
    p.add_argument(
        "--require-order-block",
        action="store_true",
        help="Require a detectable order block between sweep and MSS",
    )
    p.add_argument(
        "--require-pd-alignment",
        action="store_true",
        help="Require long in discount / short in premium of dealing range",
    )
    p.add_argument(
        "--require-ote",
        action="store_true",
        help="Require entry price inside OTE (61.8%%-79%%) of sweep-MSS impulse",
    )
    p.add_argument(
        "--require-choch",
        action="store_true",
        help="Require a recent CHOCH aligned with trade side",
    )
    p.add_argument(
        "--preset",
        choices=("none", "best", "best_fvg", "full"),
        default="none",
        help="best=HTF+session; best_fvg=+FVG; full=HTF+session+CRT+div+scoring",
    )
    p.add_argument(
        "--export-trades",
        type=Path,
        default=None,
        help="Optional path to write closed trades CSV",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    if args.preset == "best":
        args.require_htf_bias = True
        args.require_session = True
        args.session_mode = "london_ny"
    elif args.preset == "best_fvg":
        args.require_htf_bias = True
        args.require_session = True
        args.session_mode = "london_ny"
        args.entry_mode = "fvg_retrace"
    elif args.preset == "full":
        args.require_htf_bias = True
        args.require_session = True
        args.session_mode = "london_ny"
        args.require_crt_reclaim = True
        args.require_divergence = True
        args.enable_scoring = True
        args.min_score = max(int(args.min_score), 14)
        args.manage_trades = True

    csv_path = ensure_sample_csv(args.csv) if args.csv == Path("data/sample_ohlcv.csv") else args.csv
    if not csv_path.exists():
        raise SystemExit(f"CSV not found: {csv_path}")

    ohlcv = load_ohlcv(csv_path, timezone=args.timezone)
    strategy_cfg = StrategyConfig(
        swing_n=args.swing_n,
        risk_reward=args.rr,
        entry_mode=args.entry_mode,
        require_displacement=args.require_displacement,
        require_htf_bias=args.require_htf_bias,
        htf_rule=args.htf_rule,
        max_bars_sweep_to_mss=args.max_bars_sweep_mss,
        min_sweep_atr_mult=args.min_sweep_atr,
        require_session=args.require_session,
        session_mode=args.session_mode,
        timezone=args.timezone,
        require_crt_reclaim=args.require_crt_reclaim,
        require_crt_sweep=args.require_crt_sweep,
        require_divergence=args.require_divergence,
        enable_scoring=bool(args.enable_scoring),
        min_score=int(args.min_score),
        require_order_block=bool(args.require_order_block),
        require_pd_alignment=bool(args.require_pd_alignment),
        require_ote=bool(args.require_ote),
        require_choch=bool(args.require_choch),
    )
    manage_cfg = TradeManageConfig(
        enable=bool(args.manage_trades),
        breakeven_at_r=None if args.no_breakeven else args.be_at_r,
        partial_at_r=None if args.no_partial else args.partial_at_r,
        partial_fraction=args.partial_fraction,
        trail_after_r=args.trail_after_r,
        trail_step_r=args.trail_step_r,
    )
    bt_cfg = BacktestConfig(
        initial_equity=args.equity,
        risk_per_trade=args.risk,
        fee_bps=args.fee_bps,
        slippage_bps=args.slippage_bps,
        spread_bps=args.spread_bps,
        daily_loss_limit=args.daily_loss_limit,
        max_consecutive_losses=args.max_consecutive_losses,
        enable_risk_guards=not args.no_risk_guards,
        max_trades_per_day=args.max_trades_per_day,
        cooldown_bars_after_loss=args.cooldown_bars_after_loss,
        trade_manage=manage_cfg,
    )
    result = Backtester(strategy_cfg, bt_cfg).run(ohlcv)

    print("=" * 48)
    print(" Phase 1 MVP — Sweep / MSS Backtest")
    print("=" * 48)
    print(f"Bars           : {len(ohlcv)}")
    print(f"Timezone       : {args.timezone}")
    print(f"Range          : {ohlcv.index[0]} -> {ohlcv.index[-1]}")
    print(f"Entry mode     : {args.entry_mode}")
    print(f"Swing N / R:R  : {args.swing_n} / {args.rr}")
    print(f"Fee bps/fill   : {args.fee_bps}")
    print(f"Slip/Spread bps: {args.slippage_bps} / {args.spread_bps}")
    print(
        f"Risk guards    : enabled={not args.no_risk_guards} "
        f"daily_loss={args.daily_loss_limit:.1%} "
        f"max_losses={args.max_consecutive_losses}"
    )
    print(
        f"No-trade       : max_day={args.max_trades_per_day} "
        f"cooldown_bars={args.cooldown_bars_after_loss}"
    )
    print(
        f"Trade manage   : enabled={args.manage_trades} "
        f"be_at_r={None if args.no_breakeven else args.be_at_r} "
        f"partial_at_r={None if args.no_partial else args.partial_at_r} "
        f"partial_frac={args.partial_fraction} "
        f"trail_after_r={args.trail_after_r} trail_step_r={args.trail_step_r}"
    )
    print(
        f"Filters        : disp={args.require_displacement} "
        f"htf={args.require_htf_bias} session={args.require_session}:{args.session_mode} "
        f"crt_reclaim={args.require_crt_reclaim} crt_sweep={args.require_crt_sweep} "
        f"div={args.require_divergence} "
        f"max_bars={args.max_bars_sweep_mss} min_sweep_atr={args.min_sweep_atr}"
    )
    print(
        f"Scoring        : enabled={args.enable_scoring} min_score={args.min_score}/24"
    )
    print(
        f"ICT/PA         : OB={args.require_order_block} PD={args.require_pd_alignment} "
        f"OTE={args.require_ote} CHOCH={args.require_choch}"
    )
    report = check_philosophy(strategy_cfg, bt_cfg, orders_enabled=False)
    print(
        f"Philosophy     : ok={report.ok}"
        + (f" violations={list(report.violations)}" if report.violations else "")
    )
    print("-" * 48)
    print(format_metrics(result.metrics))
    print("=" * 48)

    if args.export_trades:
        rows = [
            {
                "entry_time": t.entry_time,
                "exit_time": t.exit_time,
                "side": t.side.value,
                "entry": t.entry_price,
                "stop": t.stop_loss,
                "tp": t.take_profit,
                "size": t.size,
                "exit": t.exit_price,
                "reason": t.exit_reason,
                "pnl": t.pnl,
                "partial_pnl": t.partial_pnl,
                "management": t.management_notes,
                "score": (
                    float(result.annotated["signal_score"].iloc[t.signal_index])
                    if "signal_score" in result.annotated.columns
                    and np.isfinite(result.annotated["signal_score"].iloc[t.signal_index])
                    else None
                ),
            }
            for t in result.trades
        ]
        pd.DataFrame(rows).to_csv(args.export_trades, index=False)
        print(f"Trades exported -> {args.export_trades}")


if __name__ == "__main__":
    main()
