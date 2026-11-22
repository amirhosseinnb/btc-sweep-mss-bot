"""
RSI divergence detection for AJV Rulebook §8–9.

Supports:
  - Regular bullish / bearish (reversal confirmation)
  - Hidden bullish / bearish (continuation confirmation)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_rsi(close: np.ndarray, period: int = 14) -> np.ndarray:
    """Wilder RSI; NaN until enough history exists."""
    n = len(close)
    rsi = np.full(n, np.nan, dtype=float)
    if n < period + 1:
        return rsi

    delta = np.diff(close, prepend=close[0])
    gains = np.where(delta > 0, delta, 0.0)
    losses = np.where(delta < 0, -delta, 0.0)

    avg_gain = float(np.mean(gains[1 : period + 1]))
    avg_loss = float(np.mean(losses[1 : period + 1]))
    if avg_loss == 0:
        rsi[period] = 100.0
    else:
        rs = avg_gain / avg_loss
        rsi[period] = 100.0 - (100.0 / (1.0 + rs))

    for i in range(period + 1, n):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            rsi[i] = 100.0
        else:
            rs = avg_gain / avg_loss
            rsi[i] = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def _local_extrema(values: np.ndarray, n: int, kind: str) -> list[int]:
    idxs: list[int] = []
    for i in range(n, len(values) - n):
        window = values[i - n : i + n + 1]
        center = values[i]
        if not np.isfinite(center):
            continue
        if kind == "low" and center == np.nanmin(window) and np.sum(window == center) == 1:
            idxs.append(i)
        elif kind == "high" and center == np.nanmax(window) and np.sum(window == center) == 1:
            idxs.append(i)
    return idxs


def regular_divergence_flags(
    df: pd.DataFrame,
    *,
    rsi_period: int = 14,
    swing_n: int = 3,
    lookback: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Regular divergence (reversal):

    bullish[i] = price LL + RSI HL
    bearish[i] = price HH + RSI LH
    """
    closes = df["close"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    rsi = compute_rsi(closes, period=rsi_period)

    bull = np.zeros(len(df), dtype=bool)
    bear = np.zeros(len(df), dtype=bool)

    low_ext = _local_extrema(lows, swing_n, "low")
    high_ext = _local_extrema(highs, swing_n, "high")

    for k in range(1, len(low_ext)):
        i1, i2 = low_ext[k - 1], low_ext[k]
        conf = i2 + swing_n
        if conf >= len(df) or i2 - i1 > lookback:
            continue
        r1, r2 = rsi[i1], rsi[i2]
        if not (np.isfinite(r1) and np.isfinite(r2)):
            continue
        if lows[i2] < lows[i1] and r2 > r1:
            bull[conf] = True

    for k in range(1, len(high_ext)):
        i1, i2 = high_ext[k - 1], high_ext[k]
        conf = i2 + swing_n
        if conf >= len(df) or i2 - i1 > lookback:
            continue
        r1, r2 = rsi[i1], rsi[i2]
        if not (np.isfinite(r1) and np.isfinite(r2)):
            continue
        if highs[i2] > highs[i1] and r2 < r1:
            bear[conf] = True

    return bull, bear


def hidden_divergence_flags(
    df: pd.DataFrame,
    *,
    rsi_period: int = 14,
    swing_n: int = 3,
    lookback: int = 40,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Hidden divergence (continuation):

    bullish[i] = price HL + RSI LL
    bearish[i] = price LH + RSI HH
    """
    closes = df["close"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    rsi = compute_rsi(closes, period=rsi_period)

    bull = np.zeros(len(df), dtype=bool)
    bear = np.zeros(len(df), dtype=bool)

    low_ext = _local_extrema(lows, swing_n, "low")
    high_ext = _local_extrema(highs, swing_n, "high")

    for k in range(1, len(low_ext)):
        i1, i2 = low_ext[k - 1], low_ext[k]
        conf = i2 + swing_n
        if conf >= len(df) or i2 - i1 > lookback:
            continue
        r1, r2 = rsi[i1], rsi[i2]
        if not (np.isfinite(r1) and np.isfinite(r2)):
            continue
        if lows[i2] > lows[i1] and r2 < r1:
            bull[conf] = True

    for k in range(1, len(high_ext)):
        i1, i2 = high_ext[k - 1], high_ext[k]
        conf = i2 + swing_n
        if conf >= len(df) or i2 - i1 > lookback:
            continue
        r1, r2 = rsi[i1], rsi[i2]
        if not (np.isfinite(r1) and np.isfinite(r2)):
            continue
        if highs[i2] < highs[i1] and r2 > r1:
            bear[conf] = True

    return bull, bear


def divergence_seen_recently(
    flags: np.ndarray,
    as_of: int,
    window: int,
) -> bool:
    start = max(0, as_of - window + 1)
    return bool(np.any(flags[start : as_of + 1]))
