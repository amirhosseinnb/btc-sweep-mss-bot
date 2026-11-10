"""
Download historical crypto OHLCV from Binance public API (no API key).

Example:
    python download_data.py
    python download_data.py --symbol BTCUSDT --timeframe 1h --days 365
"""

from __future__ import annotations

import argparse
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

BINANCE_KLINES = "https://api.binance.com/api/v3/klines"

TIMEFRAME_MS = {
    "1m": 60_000,
    "3m": 180_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "2h": 7_200_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
}


def fetch_klines(
    symbol: str,
    timeframe: str,
    start_ms: int,
    end_ms: int,
    *,
    limit: int = 1000,
    pause_s: float = 0.15,
) -> list[list]:
    if timeframe not in TIMEFRAME_MS:
        raise ValueError(f"Unsupported timeframe: {timeframe}. Choose from {sorted(TIMEFRAME_MS)}")

    rows: list[list] = []
    cursor = start_ms
    step = TIMEFRAME_MS[timeframe]

    while cursor < end_ms:
        params = {
            "symbol": symbol.upper(),
            "interval": timeframe,
            "startTime": cursor,
            "endTime": end_ms,
            "limit": limit,
        }
        resp = requests.get(BINANCE_KLINES, params=params, timeout=30)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break

        rows.extend(batch)
        last_open = int(batch[-1][0])
        next_cursor = last_open + step
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        time.sleep(pause_s)

    return rows


def klines_to_df(rows: list[list]) -> pd.DataFrame:
    if not rows:
        raise ValueError("No klines returned from Binance")

    df = pd.DataFrame(
        rows,
        columns=[
            "open_time",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "close_time",
            "quote_volume",
            "trades",
            "taker_buy_base",
            "taker_buy_quote",
            "ignore",
        ],
    )
    out = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(df["open_time"], unit="ms", utc=True),
            "open": pd.to_numeric(df["open"], errors="coerce"),
            "high": pd.to_numeric(df["high"], errors="coerce"),
            "low": pd.to_numeric(df["low"], errors="coerce"),
            "close": pd.to_numeric(df["close"], errors="coerce"),
            "volume": pd.to_numeric(df["volume"], errors="coerce"),
        }
    )
    out = (
        out.dropna(subset=["open", "high", "low", "close"])
        .drop_duplicates(subset=["timestamp"])
        .sort_values("timestamp")
        .reset_index(drop=True)
    )
    return out


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Download Binance OHLCV to CSV for Phase-1 backtest")
    p.add_argument("--symbol", default="BTCUSDT", help="Binance spot symbol, e.g. BTCUSDT")
    p.add_argument("--timeframe", default="1h", choices=sorted(TIMEFRAME_MS), help="Candle interval")
    p.add_argument("--days", type=int, default=365, help="Lookback window in days")
    p.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: data/{symbol}_{timeframe}.csv)",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    out = args.out or Path("data") / f"{args.symbol.lower()}_{args.timeframe}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    end = datetime.now(timezone.utc)
    start = end - timedelta(days=args.days)
    print(
        f"Downloading {args.symbol} {args.timeframe} "
        f"from {start.date()} to {end.date()} ..."
    )

    rows = fetch_klines(
        args.symbol,
        args.timeframe,
        int(start.timestamp() * 1000),
        int(end.timestamp() * 1000),
    )
    df = klines_to_df(rows)
    df.to_csv(out, index=False)

    print(f"Saved {len(df)} bars -> {out.resolve()}")
    print(f"Range: {df['timestamp'].iloc[0]} -> {df['timestamp'].iloc[-1]}")
    print(f"Last close: {df['close'].iloc[-1]:.2f}")


if __name__ == "__main__":
    main()
