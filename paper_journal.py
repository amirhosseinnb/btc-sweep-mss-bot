"""
Paper journal: append-only checks, resolve SL/TP outcomes, readiness gates.

No live orders. Used by CI + local paper runs to accumulate out-of-sample evidence
before Phase-2 Demo/Testnet.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd

from core_strategy import Side, generate_signals
from download_data import TIMEFRAME_MS
from jalali import dual_date
from paper_trader import (
    already_logged,
    append_signal_log,
    fetch_closed_ohlcv,
    signal_to_row,
    strategy_for_preset,
)

DEFAULT_SYMBOLS = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
CHECKS_PATH = Path("data/paper_checks.csv")
SIGNALS_PATH = Path("data/paper_signals.csv")
OUTCOMES_PATH = Path("data/paper_outcomes.json")
READINESS_PATH = Path("data/paper_readiness.json")

# Forward-test gates before Phase-2 (Demo). Progress is tracked even when not met.
READINESS_GATES = {
    "min_closed_paper_trades": 30,
    "min_paper_win_rate": 0.55,
    "min_btc_javid_profit_factor": 1.5,
    "min_wf_javid_positive_ratio": 0.50,
}


def append_check_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        frame.to_csv(path, mode="a", header=False, index=False)
    else:
        frame.to_csv(path, index=False)


def _side_from_row(side: str) -> Side:
    return Side.LONG if str(side).lower() == "long" else Side.SHORT


def resolve_signal_outcome(
    *,
    side: str,
    entry: float,
    stop: float,
    take_profit: float,
    signal_time: pd.Timestamp,
    ohlcv: pd.DataFrame,
) -> dict:
    """Walk bars after signal; conservative: SL before TP if both touch."""
    if ohlcv.empty:
        return {"status": "no_data", "exit_reason": None, "bars_held": 0}

    idx = ohlcv.index
    # Align timezone
    target = pd.Timestamp(signal_time)
    if target.tzinfo is None:
        target = target.tz_localize(idx.tz)
    else:
        target = target.tz_convert(idx.tz)

    after = ohlcv[idx > target]
    if after.empty:
        return {"status": "open", "exit_reason": None, "bars_held": 0}

    side_e = _side_from_row(side)
    for i, (ts, row) in enumerate(after.iterrows(), start=1):
        high = float(row["high"])
        low = float(row["low"])
        hit_sl = low <= stop if side_e is Side.LONG else high >= stop
        hit_tp = high >= take_profit if side_e is Side.LONG else low <= take_profit
        if hit_sl and hit_tp:
            exit_px, reason = stop, "stop_loss"
        elif hit_sl:
            exit_px, reason = stop, "stop_loss"
        elif hit_tp:
            exit_px, reason = take_profit, "take_profit"
        else:
            continue
        if side_e is Side.LONG:
            pnl_r = (exit_px - entry) / abs(entry - stop) if entry != stop else 0.0
        else:
            pnl_r = (entry - exit_px) / abs(entry - stop) if entry != stop else 0.0
        return {
            "status": "closed",
            "exit_reason": reason,
            "exit_time": ts.isoformat(),
            "exit_price": float(exit_px),
            "bars_held": i,
            "pnl_r": float(pnl_r),
            "win": bool(pnl_r > 0),
        }
    return {"status": "open", "exit_reason": None, "bars_held": int(len(after))}


def load_signal_log(path: Path = SIGNALS_PATH) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty:
        return df
    if "outcome_status" not in df.columns:
        df["outcome_status"] = "pending"
    return df


def update_signal_outcomes(
    *,
    signals_path: Path = SIGNALS_PATH,
    ohlcv_cache: Optional[dict[str, pd.DataFrame]] = None,
    days: int = 400,
) -> dict:
    """Resolve pending paper signals against closed candles; rewrite CSV with outcomes."""
    from run import load_ohlcv

    df = load_signal_log(signals_path)
    if df.empty:
        summary = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_signals": 0,
            "n_closed": 0,
            "n_open": 0,
            "n_wins": 0,
            "win_rate": 0.0,
            "avg_pnl_r": 0.0,
        }
        OUTCOMES_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUTCOMES_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        return summary

    cache = dict(ohlcv_cache or {})
    closed_pnls: list[float] = []
    n_open = 0

    for i, row in df.iterrows():
        status = str(row.get("outcome_status") or "pending")
        if status == "closed":
            if pd.notna(row.get("pnl_r")):
                closed_pnls.append(float(row["pnl_r"]))
            continue

        symbol = str(row.get("symbol") or "BTCUSDT").upper()
        timeframe = str(row.get("timeframe") or "4h")
        key = f"{symbol}_{timeframe}"
        if key not in cache:
            local = Path("data") / f"{symbol.lower()}_{timeframe}.csv"
            if local.exists():
                cache[key] = load_ohlcv(local)
            else:
                cache[key] = fetch_closed_ohlcv(symbol, timeframe, days)

        outcome = resolve_signal_outcome(
            side=str(row["side"]),
            entry=float(row["entry"]),
            stop=float(row["stop_loss"]),
            take_profit=float(row["take_profit"]),
            signal_time=pd.Timestamp(row["signal_time"]),
            ohlcv=cache[key],
        )
        df.at[i, "outcome_status"] = outcome["status"]
        df.at[i, "exit_reason"] = outcome.get("exit_reason")
        df.at[i, "exit_time"] = outcome.get("exit_time")
        df.at[i, "exit_price"] = outcome.get("exit_price")
        df.at[i, "bars_held"] = outcome.get("bars_held")
        df.at[i, "pnl_r"] = outcome.get("pnl_r")
        df.at[i, "win"] = outcome.get("win")
        if outcome["status"] == "closed":
            closed_pnls.append(float(outcome["pnl_r"]))
        elif outcome["status"] == "open":
            n_open += 1

    signals_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(signals_path, index=False)

    wins = sum(1 for x in closed_pnls if x > 0)
    summary = {
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "n_signals": int(len(df)),
        "n_closed": int(len(closed_pnls)),
        "n_open": int(n_open),
        "n_wins": int(wins),
        "win_rate": (wins / len(closed_pnls)) if closed_pnls else 0.0,
        "avg_pnl_r": float(sum(closed_pnls) / len(closed_pnls)) if closed_pnls else 0.0,
    }
    OUTCOMES_PATH.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def seed_historical_signals(
    *,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    timeframe: str = "4h",
    days: int = 400,
    preset: str = "javid",
    log_path: Path = SIGNALS_PATH,
    max_per_symbol: int = 40,
) -> int:
    """Backfill closed-bar historical signals into the paper log (source=historical)."""
    from run import load_ohlcv

    added = 0
    checked_at = datetime.now(timezone.utc).isoformat()
    for symbol in symbols:
        local = Path("data") / f"{symbol.lower()}_{timeframe}.csv"
        if local.exists():
            ohlcv = load_ohlcv(local)
            if days > 0 and len(ohlcv) > 0:
                cutoff = ohlcv.index.max() - pd.Timedelta(days=days)
                ohlcv = ohlcv[ohlcv.index >= cutoff]
        else:
            ohlcv = fetch_closed_ohlcv(symbol, timeframe, days)
        cfg = strategy_for_preset(preset)
        _, signals = generate_signals(ohlcv, cfg)
        # Skip the newest bar (still "live"); seed older closed setups.
        for sig in signals[-max_per_symbol:]:
            if sig.index >= len(ohlcv) - 1:
                continue
            bar_time = ohlcv.index[sig.index]
            if already_logged(log_path, bar_time, symbol=symbol):
                continue
            row = signal_to_row(
                sig=sig,
                last_bar_time=bar_time,
                checked_at=checked_at,
                symbol=symbol,
                timeframe=timeframe,
                mark=float(ohlcv["close"].iloc[sig.index]),
                preset=preset,
            )
            row["source"] = "historical_seed"
            row["status"] = "paper_signal_only"
            append_signal_log(log_path, row)
            added += 1
    return added


def build_readiness(
    *,
    paper_outcomes: dict,
    markets_javid: list[dict],
    wf_javid: dict,
) -> dict:
    gates = READINESS_GATES
    btc = next((m for m in markets_javid if m.get("name") == "BTC"), None)
    btc_pf = float(btc["profit_factor"]) if btc and btc.get("profit_factor") is not None else 0.0
    wf_total = int(wf_javid.get("total_folds") or 0)
    wf_pos = int(wf_javid.get("positive_folds") or 0)
    wf_ratio = (wf_pos / wf_total) if wf_total else 0.0

    closed = int(paper_outcomes.get("n_closed") or 0)
    paper_wr = float(paper_outcomes.get("win_rate") or 0.0)

    checks = [
        {
            "id": "paper_sample",
            "title_fa": f"حداقل {gates['min_closed_paper_trades']} معاملهٔ Paper بسته‌شده",
            "current": closed,
            "target": gates["min_closed_paper_trades"],
            "ok": closed >= gates["min_closed_paper_trades"],
        },
        {
            "id": "paper_win_rate",
            "title_fa": f"Win-rate Paper ≥ {gates['min_paper_win_rate']:.0%}",
            "current": round(paper_wr, 4),
            "target": gates["min_paper_win_rate"],
            "ok": closed > 0 and paper_wr >= gates["min_paper_win_rate"],
        },
        {
            "id": "btc_javid_pf",
            "title_fa": f"Profit Factor قوانین کامل BTC ≥ {gates['min_btc_javid_profit_factor']}",
            "current": round(btc_pf, 4),
            "target": gates["min_btc_javid_profit_factor"],
            "ok": btc_pf >= gates["min_btc_javid_profit_factor"],
        },
        {
            "id": "wf_javid",
            "title_fa": f"نسبت فولد مثبت WF ≥ {gates['min_wf_javid_positive_ratio']:.0%}",
            "current": round(wf_ratio, 4),
            "target": gates["min_wf_javid_positive_ratio"],
            "ok": wf_ratio >= gates["min_wf_javid_positive_ratio"],
        },
    ]
    ready = all(c["ok"] for c in checks)
    now = dual_date(datetime.now(timezone.utc), with_time=True)
    payload = {
        "updated_at": now,
        "phase2_ready": ready,
        "verdict_fa": (
            "آمادگی Demo/Testnet تأیید شد"
            if ready
            else "هنوز برای فاز بعد آماده نیست — جمع‌آوری شواهد Paper ادامه دارد"
        ),
        "gates": checks,
        "paper": paper_outcomes,
        "note_fa": "Train مدل ML انجام نمی‌شود؛ آمادگی فقط با شواهد قانون‌محور و Paper سنجیده می‌شود.",
    }
    READINESS_PATH.parent.mkdir(parents=True, exist_ok=True)
    READINESS_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def run_multi_symbol_check(
    *,
    symbols: tuple[str, ...] = DEFAULT_SYMBOLS,
    timeframe: str = "4h",
    days: int = 400,
    preset: str = "javid",
    signals_path: Path = SIGNALS_PATH,
    checks_path: Path = CHECKS_PATH,
) -> list[dict]:
    """One paper pass across symbols: log checks + new signals."""
    from paper_trader import evaluate_once

    snapshots: list[dict] = []
    for symbol in symbols:
        snap = evaluate_once(
            symbol=symbol,
            timeframe=timeframe,
            days=days,
            log_path=signals_path,
            state_path=Path(f"data/paper_state_{symbol.lower()}.json"),
            preset=preset,
            checks_path=checks_path,
        )
        snapshots.append(snap)
    # Keep BTC as the canonical state file for older tools.
    btc = next((s for s in snapshots if s.get("symbol") == "BTCUSDT"), None)
    if btc:
        Path("data/paper_state.json").write_text(
            json.dumps(btc, indent=2, default=str), encoding="utf-8"
        )
    return snapshots


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Paper journal / readiness tools")
    p.add_argument("--seed", action="store_true", help="Seed historical signals into paper log")
    p.add_argument("--resolve", action="store_true", help="Resolve open paper outcomes")
    p.add_argument("--check", action="store_true", help="Run multi-symbol paper check")
    p.add_argument("--days", type=int, default=400)
    p.add_argument("--preset", default="javid")
    args = p.parse_args()

    if args.seed:
        n = seed_historical_signals(days=args.days, preset=args.preset)
        print(f"Seeded {n} historical paper signals")
    if args.check:
        snaps = run_multi_symbol_check(days=args.days, preset=args.preset)
        print(f"Checked {len(snaps)} symbols")
    if args.resolve or args.seed or args.check:
        summary = update_signal_outcomes(days=args.days)
        print(
            f"Outcomes | signals={summary['n_signals']} closed={summary['n_closed']} "
            f"open={summary['n_open']} WR={summary['win_rate']:.1%}"
        )


if __name__ == "__main__":
    main()
