"""
Price Action framework helpers for AJV.

Builds on swing points to classify:
  - BOS  (Break of Structure): continuation break with prior trend
  - CHOCH (Change of Character): first break against prior trend
  - Impulse vs retracement legs between swings
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np
import pandas as pd

from core_strategy import Side, SwingPoint


class StructureKind(str, Enum):
    BOS = "bos"
    CHOCH = "choch"


@dataclass(frozen=True, slots=True)
class StructureEvent:
    index: int  # confirmation / break bar
    kind: StructureKind
    side: Side  # LONG = bullish break, SHORT = bearish break
    broken_level: float
    prior_trend: int  # +1 bullish, -1 bearish, 0 unknown


@dataclass(frozen=True, slots=True)
class PriceLeg:
    start_index: int
    end_index: int
    start_price: float
    end_price: float
    kind: str  # "impulse" | "retracement"

    @property
    def bullish(self) -> bool:
        return self.end_price > self.start_price

    @property
    def size(self) -> float:
        return abs(self.end_price - self.start_price)


def _confirmed_swings_sorted(swings: list[SwingPoint]) -> list[SwingPoint]:
    return sorted(swings, key=lambda s: (s.confirmed_at, s.index))


def infer_structure_events(
    df: pd.DataFrame,
    swings: list[SwingPoint],
) -> list[StructureEvent]:
    """
    Walk confirmed swings and emit BOS/CHOCH when a later close breaks the
    most recent opposite swing.
    """
    closes = df["close"].to_numpy(dtype=float)
    ordered = _confirmed_swings_sorted(swings)
    if not ordered:
        return []

    events: list[StructureEvent] = []
    last_high: Optional[SwingPoint] = None
    last_low: Optional[SwingPoint] = None
    trend = 0  # +1 bull, -1 bear

    for sw in ordered:
        if sw.kind == "high":
            last_high = sw
        else:
            last_low = sw

        # From confirmation bar forward, look for the first close break.
        start = sw.confirmed_at
        for i in range(start, len(closes)):
            if sw.kind == "low" and last_high is not None and closes[i] > last_high.price:
                kind = StructureKind.BOS if trend >= 0 else StructureKind.CHOCH
                events.append(
                    StructureEvent(
                        index=i,
                        kind=kind,
                        side=Side.LONG,
                        broken_level=float(last_high.price),
                        prior_trend=trend,
                    )
                )
                trend = 1
                break
            if sw.kind == "high" and last_low is not None and closes[i] < last_low.price:
                kind = StructureKind.BOS if trend <= 0 else StructureKind.CHOCH
                events.append(
                    StructureEvent(
                        index=i,
                        kind=kind,
                        side=Side.SHORT,
                        broken_level=float(last_low.price),
                        prior_trend=trend,
                    )
                )
                trend = -1
                break
    return events


def latest_structure_before(
    events: list[StructureEvent],
    *,
    index: int,
    side: Optional[Side] = None,
) -> Optional[StructureEvent]:
    chosen: Optional[StructureEvent] = None
    for ev in events:
        if ev.index > index:
            break
        if side is not None and ev.side is not side:
            continue
        chosen = ev
    return chosen


def build_legs_from_swings(swings: list[SwingPoint]) -> list[PriceLeg]:
    """
    Alternate swing high/low sequence -> legs.
    A leg larger than the previous opposite leg is tagged impulse; else retracement.
    """
    ordered = sorted(swings, key=lambda s: s.index)
    if len(ordered) < 2:
        return []

    legs: list[PriceLeg] = []
    prev_size = 0.0
    for a, b in zip(ordered, ordered[1:]):
        if a.kind == b.kind:
            continue
        size = abs(b.price - a.price)
        kind = "impulse" if size >= prev_size and prev_size > 0 else (
            "impulse" if prev_size == 0 else "retracement"
        )
        # First leg always impulse seed.
        if prev_size == 0:
            kind = "impulse"
        legs.append(
            PriceLeg(
                start_index=a.index,
                end_index=b.index,
                start_price=float(a.price),
                end_price=float(b.price),
                kind=kind,
            )
        )
        prev_size = size
    return legs


def active_dealing_range(
    swings: list[SwingPoint],
    *,
    asof_index: int,
) -> Optional[tuple[float, float, int, int]]:
    """
    Most recent completed swing high + swing low pair at/before asof_index.
    Returns (low, high, low_index, high_index) or None.
    """
    highs = [s for s in swings if s.kind == "high" and s.index <= asof_index]
    lows = [s for s in swings if s.kind == "low" and s.index <= asof_index]
    if not highs or not lows:
        return None
    last_high = max(highs, key=lambda s: s.index)
    last_low = max(lows, key=lambda s: s.index)
    lo = float(min(last_low.price, last_high.price))
    hi = float(max(last_low.price, last_high.price))
    if hi <= lo:
        return None
    return lo, hi, last_low.index, last_high.index
