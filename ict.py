"""
ICT microstructure helpers: Fair Value Gaps (FVG).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from core_strategy import Side


@dataclass(frozen=True, slots=True)
class FairValueGap:
    index: int  # confirming candle index (candle 3)
    side: Side  # LONG = bullish FVG, SHORT = bearish FVG
    bottom: float
    top: float

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.bottom + self.top)


def detect_fvgs(df: pd.DataFrame) -> list[FairValueGap]:
    """
    3-candle FVG definition:

    Bullish: Low[i] > High[i-2]  -> zone [High[i-2], Low[i]]
    Bearish: High[i] < Low[i-2]  -> zone [High[i], Low[i-2]]
    """
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    gaps: list[FairValueGap] = []

    for i in range(2, len(df)):
        if lows[i] > highs[i - 2]:
            gaps.append(
                FairValueGap(
                    index=i,
                    side=Side.LONG,
                    bottom=float(highs[i - 2]),
                    top=float(lows[i]),
                )
            )
        if highs[i] < lows[i - 2]:
            gaps.append(
                FairValueGap(
                    index=i,
                    side=Side.SHORT,
                    bottom=float(highs[i]),
                    top=float(lows[i - 2]),
                )
            )
    return gaps


def latest_fvg_between(
    gaps: list[FairValueGap],
    *,
    side: Side,
    start_index: int,
    end_index: int,
) -> FairValueGap | None:
    """Most recent directional FVG with confirming bar in [start_index, end_index]."""
    chosen: FairValueGap | None = None
    for gap in gaps:
        if gap.side is not side:
            continue
        if start_index <= gap.index <= end_index:
            chosen = gap
    return chosen


def fvg_touched(gap: FairValueGap, high: float, low: float) -> bool:
    """True when bar range overlaps the FVG zone."""
    return low <= gap.top and high >= gap.bottom


def fvg_entry_price(gap: FairValueGap, close: float) -> float:
    """
    Conservative fill inside the gap:
    - long: min(close, midpoint)
    - short: max(close, midpoint)
    """
    mid = gap.midpoint
    if gap.side is Side.LONG:
        return float(min(close, mid))
    return float(max(close, mid))
