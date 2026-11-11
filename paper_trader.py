"""
Read-only BTC 4H paper signal runner (no live orders).

Fetches Binance public klines, evaluates the `best` preset on *closed*
candles only, and appends new signals to a CSV log.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

from core_strategy import DEFAULT_TIMEZONE, generate_signals, to_project_timezone
from download_data import TIMEFRAME_MS, fetch_klines, fetch_ticker_price, klines_to_df
from validate import best_strategy_config


def fetch_closed_ohlcv(
    symbol: str,
    timeframe: str,
    days: int,
    timezone_name: str = DEFAULT_TIMEZONE,
) -> pd.DataFrame:
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)
    rows = fetch_klines(
        symbol,
        timeframe,
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000),
    )
    raw = klines_to_df(rows)
    raw["timestamp"] = pd.to_datetime(raw["timestamp"], utc=True)
    df = raw.set_index("timestamp").sort_index()
    df.index = to_project_timezone(df.index, timezone=timezone_name)

    # Drop the currently forming candle (open_time + interval > now).
    interval_ms = TIMEFRAME_MS[timeframe]
    now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    # Index is NY-local; convert back to UTC ms via tz_convert.
    open_ms = (df.index.tz_convert("UTC").asi8 // 10**6).astype("int64")
    closed_mask = open_ms + interval_ms <= now_ms
    closed = df.loc[closed_mask].copy()
    if closed.empty:
        raise RuntimeError("No closed candles available yet")
    return closed


def latest_mark_price(symbol: str) -> float:
    return fetch_ticker_price(symbol)


def append_signal_log(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame([row])
    if path.exists():
        frame.to_csv(path, mode="a", header=False, index=False)
    else:
        frame.to_csv(path, index=False)


def already_logged(path: Path, signal_time: pd.Timestamp) -> bool:
    if not path.exists():
        return False
    prev = pd.read_csv(path)
    if "signal_time" not in prev.columns or prev.empty:
        return False
    times = pd.to_datetime(prev["signal_time"], utc=True)
    target = pd.Timestamp(signal_time)
    if target.tzinfo is None:
        target = target.tz_localize("UTC")
    else:
        target = target.tz_convert("UTC")
    return bool((times == target).any())


def seconds_until_next_close(timeframe: str) -> int:
    interval = TIMEFRAME_MS[timeframe] // 1000
    now = int(datetime.now(timezone.utc).timestamp())
    # Align to UTC epoch boundaries used by Binance.
    nxt = ((now // interval) + 1) * interval
    return max(5, nxt - now + 2)  # +2s buffer after close


def evaluate_once(
    *,
    symbol: str,
    timeframe: str,
    days: int,
    log_path: Path,
    state_path: Path,
) -> dict:
    ohlcv = fetch_closed_ohlcv(symbol, timeframe, days)
    cfg = best_strategy_config()
    annotated, signals = generate_signals(ohlcv, cfg)
    mark = latest_mark_price(symbol)

    last_bar_time = ohlcv.index[-1]
    last_close = float(ohlcv["close"].iloc[-1])
    active = [s for s in signals if s.index == len(ohlcv) - 1]

    snapshot = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "last_closed_bar": str(last_bar_time),
        "last_close": last_close,
        "mark_price": mark,
        "n_bars": len(ohlcv),
        "n_signals_total": len(signals),
        "new_signal": False,
    }

    if not active:
        print(
            f"[{snapshot['checked_at_utc']}] {symbol} {timeframe} | "
            f"last_bar={last_bar_time} close={last_close:.2f} mark={mark:.2f} | NO new signal"
        )
    else:
        sig = active[0]
        if already_logged(log_path, last_bar_time):
            print(
                f"[{snapshot['checked_at_utc']}] Signal already logged for {last_bar_time}"
            )
        else:
            row = {
                "signal_time": last_bar_time.isoformat(),
                "checked_at_utc": snapshot["checked_at_utc"],
                "symbol": symbol.upper(),
                "timeframe": timeframe,
                "side": sig.side.value,
                "entry": sig.entry,
                "stop_loss": sig.stop_loss,
                "take_profit": sig.take_profit,
                "risk_reward": sig.risk_reward,
                "score": sig.score,
                "score_detail": sig.score_detail,
                "mark_price": mark,
                "status": "paper_signal_only",
            }
            append_signal_log(log_path, row)
            snapshot["new_signal"] = True
            snapshot["signal"] = row
            print("=" * 60)
            print(" PAPER SIGNAL (no order sent)")
            print("=" * 60)
            print(f"Time   : {last_bar_time}")
            print(f"Side   : {sig.side.value.upper()}")
            print(f"Entry  : {sig.entry:.2f}")
            print(f"SL     : {sig.stop_loss:.2f}")
            print(f"TP     : {sig.take_profit:.2f}")
            if sig.score is not None:
                print(f"Score  : {sig.score_detail or sig.score}")
            print(f"Mark   : {mark:.2f}")
            print(f"Logged : {log_path}")
            print("=" * 60)

    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    return snapshot


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="BTC 4H read-only paper signal runner")
    p.add_argument("--symbol", default="BTCUSDT")
    p.add_argument("--timeframe", default="4h", choices=sorted(TIMEFRAME_MS))
    p.add_argument("--days", type=int, default=400, help="History window for indicators")
    p.add_argument("--once", action="store_true", help="Run a single check and exit")
    p.add_argument(
        "--log",
        type=Path,
        default=Path("data/paper_signals.csv"),
        help="Append-only signal log",
    )
    p.add_argument(
        "--state",
        type=Path,
        default=Path("data/paper_state.json"),
        help="Latest status JSON",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    print(
        f"Paper trader starting | {args.symbol} {args.timeframe} | "
        f"read-only | timezone={DEFAULT_TIMEZONE}"
    )
    if args.once:
        evaluate_once(
            symbol=args.symbol,
            timeframe=args.timeframe,
            days=args.days,
            log_path=args.log,
            state_path=args.state,
        )
        return

    while True:
        try:
            evaluate_once(
                symbol=args.symbol,
                timeframe=args.timeframe,
                days=args.days,
                log_path=args.log,
                state_path=args.state,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"Error: {exc}")
        sleep_s = seconds_until_next_close(args.timeframe)
        # In loop mode, also refresh periodically inside the candle.
        sleep_s = min(sleep_s, 15 * 60)
        print(f"Sleeping {sleep_s}s ...")
        time.sleep(sleep_s)


if __name__ == "__main__":
    main()
