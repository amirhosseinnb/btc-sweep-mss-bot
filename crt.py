"""
Candle Range Theory (CRT) helpers for Phase 1.6.

Builds previous completed New York daily ranges and evaluates reclaim
after a liquidity sweep.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from core_strategy import DEFAULT_TIMEZONE, Side, to_project_timezone


def compute_prior_day_crt_levels(
    df: pd.DataFrame,
    timezone: str = DEFAULT_TIMEZONE,
) -> tuple[np.ndarray, np.ndarray]:
    """
    For each LTF bar, return the prior *completed* NY-day high/low.

    No look-ahead: bar T only sees the daily candle that finished before T.
    """
    if not isinstance(df.index, pd.DatetimeIndex):
        raise ValueError("CRT levels require a DatetimeIndex")

    local = df.copy()
    local.index = to_project_timezone(df.index, timezone=timezone)
    # Resample on NY wall clock (tz-naive local), then shift by 1 day.
    flat = local.copy()
    flat.index = local.index.tz_localize(None)

    daily = (
        flat.resample("1D", label="left", closed="left")
        .agg({"high": "max", "low": "min"})
        .dropna()
    )
    prior_high = daily["high"].shift(1)
    prior_low = daily["low"].shift(1)

    crt_high = prior_high.reindex(flat.index, method="ffill")
    crt_low = prior_low.reindex(flat.index, method="ffill")
    return (
        crt_high.to_numpy(dtype=float),
        crt_low.to_numpy(dtype=float),
    )


def is_reclaim_close(
    side: Side,
    close: float,
    crt_high: float,
    crt_low: float,
) -> bool:
    """
    Reclaim = close back inside the CRT range after sweeping a boundary.

    Bullish: close strictly above CRT low and at/below CRT high.
    Bearish: close strictly below CRT high and at/above CRT low.
    """
    if not np.isfinite(crt_high) or not np.isfinite(crt_low):
        return False
    if crt_high < crt_low:
        return False
    if side is Side.LONG:
        return crt_low < close <= crt_high
    return crt_low <= close < crt_high


def pierces_crt_boundary(
    side: Side,
    high: float,
    low: float,
    crt_high: float,
    crt_low: float,
) -> bool:
    """True if the bar wick pierces the CRT side being hunted."""
    if not np.isfinite(crt_high) or not np.isfinite(crt_low):
        return False
    if side is Side.LONG:
        return low < crt_low
    return high > crt_high
