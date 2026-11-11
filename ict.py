"""
ICT microstructure helpers for AJV.

Includes:
  - Fair Value Gaps (FVG)
  - Order Blocks (simplified last opposing candle before displacement)
  - Premium / Discount dealing-range location
  - OTE (Optimal Trade Entry: 61.8%–79% retracement of impulse)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

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


@dataclass(frozen=True, slots=True)
class OrderBlock:
    index: int  # candle index of the OB
    side: Side  # LONG = bullish OB (demand), SHORT = bearish OB (supply)
    bottom: float
    top: float
    mss_index: int

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.bottom + self.top)


@dataclass(frozen=True, slots=True)
class OTEZone:
    side: Side
    bottom: float
    top: float
    impulse_low: float
    impulse_high: float

    def contains(self, price: float) -> bool:
        return self.bottom <= price <= self.top


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


def find_order_block(
    df: pd.DataFrame,
    *,
    side: Side,
    sweep_index: int,
    mss_index: int,
) -> Optional[OrderBlock]:
    """
    Simplified ICT order block:

    Bullish OB = last bearish (close < open) candle in (sweep, mss]
    Bearish OB = last bullish (close > open) candle in (sweep, mss]
    """
    if mss_index <= sweep_index:
        return None
    opens = df["open"].to_numpy(dtype=float)
    closes = df["close"].to_numpy(dtype=float)
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)

    chosen_i: Optional[int] = None
    for i in range(sweep_index + 1, mss_index + 1):
        if side is Side.LONG and closes[i] < opens[i]:
            chosen_i = i
        elif side is Side.SHORT and closes[i] > opens[i]:
            chosen_i = i
    if chosen_i is None:
        # Fallback: candle immediately before MSS.
        chosen_i = max(sweep_index, mss_index - 1)
    return OrderBlock(
        index=int(chosen_i),
        side=side,
        bottom=float(lows[chosen_i]),
        top=float(highs[chosen_i]),
        mss_index=mss_index,
    )


def order_block_touched(ob: OrderBlock, high: float, low: float) -> bool:
    return low <= ob.top and high >= ob.bottom


def ote_zone_from_impulse(
    *,
    side: Side,
    impulse_low: float,
    impulse_high: float,
    fib_low: float = 0.618,
    fib_high: float = 0.79,
) -> Optional[OTEZone]:
    """
    OTE as Fibonacci retracement band of the impulse leg.

    Long: buy discount OTE measured from impulse low->high
    Short: sell premium OTE measured from impulse high->low
    """
    if impulse_high <= impulse_low:
        return None
    span = impulse_high - impulse_low
    if side is Side.LONG:
        # Retrace from high toward low: 61.8%–79% down from high.
        top = impulse_high - fib_low * span
        bottom = impulse_high - fib_high * span
    else:
        # Retrace from low toward high: 61.8%–79% up from low.
        bottom = impulse_low + fib_low * span
        top = impulse_low + fib_high * span
    if top < bottom:
        bottom, top = top, bottom
    return OTEZone(
        side=side,
        bottom=float(bottom),
        top=float(top),
        impulse_low=float(impulse_low),
        impulse_high=float(impulse_high),
    )


def impulse_from_sweep_mss(
    *,
    side: Side,
    sweep_extreme: float,
    mss_close: float,
) -> Optional[tuple[float, float]]:
    """Impulse range used for OTE after Sweep->MSS."""
    if side is Side.LONG:
        lo, hi = float(sweep_extreme), float(mss_close)
    else:
        lo, hi = float(mss_close), float(sweep_extreme)
    if hi <= lo:
        return None
    return lo, hi


def is_in_discount(price: float, range_low: float, range_high: float) -> bool:
    if range_high <= range_low:
        return False
    eq = 0.5 * (range_low + range_high)
    return price <= eq


def is_in_premium(price: float, range_low: float, range_high: float) -> bool:
    if range_high <= range_low:
        return False
    eq = 0.5 * (range_low + range_high)
    return price >= eq


def pd_aligned_for_side(
    side: Side,
    price: float,
    range_low: float,
    range_high: float,
) -> bool:
    """Longs prefer discount; shorts prefer premium."""
    if side is Side.LONG:
        return is_in_discount(price, range_low, range_high)
    return is_in_premium(price, range_low, range_high)
