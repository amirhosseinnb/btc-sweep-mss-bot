"""
In-trade management for Phase 1: breakeven, partial take-profit, trailing stop.

All features are optional and off by default so baseline Sweep/MSS results stay stable.
Distances are measured in R units where 1R = abs(entry - initial_stop).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core_strategy import Side


@dataclass(frozen=True)
class TradeManageConfig:
    enable: bool = False
    # Move stop to entry (+ optional buffer) once favorable excursion reaches this R.
    breakeven_at_r: Optional[float] = 1.0
    breakeven_buffer_bps: float = 0.0
    # Close a fraction of size at this R; remainder keeps original TP.
    partial_at_r: Optional[float] = 1.0
    partial_fraction: float = 0.5
    # After this R, trail stop behind the favorable extreme by trail_step_r.
    trail_after_r: Optional[float] = None
    trail_step_r: float = 0.5

    def __post_init__(self) -> None:
        if self.breakeven_at_r is not None and self.breakeven_at_r <= 0:
            raise ValueError("breakeven_at_r must be > 0")
        if self.partial_at_r is not None and self.partial_at_r <= 0:
            raise ValueError("partial_at_r must be > 0")
        if not 0.0 < self.partial_fraction < 1.0:
            raise ValueError("partial_fraction must be in (0, 1)")
        if self.trail_after_r is not None and self.trail_after_r <= 0:
            raise ValueError("trail_after_r must be > 0")
        if self.trail_step_r <= 0:
            raise ValueError("trail_step_r must be > 0")
        if self.breakeven_buffer_bps < 0:
            raise ValueError("breakeven_buffer_bps must be >= 0")


@dataclass
class ManagedTradeState:
    initial_stop: float
    risk_distance: float
    original_size: float
    remaining_size: float
    breakeven_applied: bool = False
    partial_taken: bool = False
    best_favorable: Optional[float] = None


def initial_state(side: Side, entry: float, stop: float, size: float) -> ManagedTradeState:
    risk = abs(entry - stop)
    if risk <= 0 or size <= 0:
        raise ValueError("invalid trade distances/size for management")
    return ManagedTradeState(
        initial_stop=stop,
        risk_distance=risk,
        original_size=size,
        remaining_size=size,
    )


def _favorable_extreme(side: Side, bar_high: float, bar_low: float) -> float:
    return bar_high if side is Side.LONG else bar_low


def _r_multiple(side: Side, entry: float, extreme: float, risk_distance: float) -> float:
    if side is Side.LONG:
        return (extreme - entry) / risk_distance
    return (entry - extreme) / risk_distance


def _breakeven_stop(side: Side, entry: float, buffer_bps: float) -> float:
    mult = buffer_bps / 10_000.0
    if side is Side.LONG:
        return entry * (1.0 + mult)
    return entry * (1.0 - mult)


def _tighten_stop(side: Side, current_stop: float, candidate: float) -> float:
    if side is Side.LONG:
        return max(current_stop, candidate)
    return min(current_stop, candidate)


@dataclass
class ManagementAction:
    new_stop: Optional[float] = None
    partial_price: Optional[float] = None
    partial_size: Optional[float] = None
    notes: tuple[str, ...] = ()


def manage_open_trade(
    *,
    side: Side,
    entry: float,
    stop_loss: float,
    take_profit: float,
    bar_high: float,
    bar_low: float,
    state: ManagedTradeState,
    config: TradeManageConfig,
) -> ManagementAction:
    """
    Update management from the current bar's range.

    Returns optional new stop and/or a partial fill at the configured R level.
    Caller still evaluates full SL/TP exits with the (possibly updated) stop.
    """
    if not config.enable or state.remaining_size <= 0:
        return ManagementAction()

    extreme = _favorable_extreme(side, bar_high, bar_low)
    if state.best_favorable is None:
        state.best_favorable = extreme
    else:
        if side is Side.LONG:
            state.best_favorable = max(state.best_favorable, extreme)
        else:
            state.best_favorable = min(state.best_favorable, extreme)

    r_now = _r_multiple(side, entry, extreme, state.risk_distance)
    r_best = _r_multiple(side, entry, state.best_favorable, state.risk_distance)
    notes: list[str] = []
    new_stop = stop_loss
    partial_price: Optional[float] = None
    partial_size: Optional[float] = None

    # 1) Partial at configured R (once).
    if (
        not state.partial_taken
        and config.partial_at_r is not None
        and r_now >= config.partial_at_r
    ):
        move = config.partial_at_r * state.risk_distance
        if side is Side.LONG:
            partial_price = entry + move
        else:
            partial_price = entry - move
        partial_size = state.original_size * config.partial_fraction
        # Never partial more than remaining.
        partial_size = min(partial_size, state.remaining_size * 0.999999)
        if partial_size > 0:
            state.partial_taken = True
            state.remaining_size -= partial_size
            notes.append("partial_tp")

    # 2) Breakeven stop.
    if (
        not state.breakeven_applied
        and config.breakeven_at_r is not None
        and r_best >= config.breakeven_at_r
    ):
        be = _breakeven_stop(side, entry, config.breakeven_buffer_bps)
        tightened = _tighten_stop(side, new_stop, be)
        if tightened != new_stop:
            new_stop = tightened
            notes.append("breakeven")
        state.breakeven_applied = True

    # 3) Trailing stop after trail_after_r, based on best favorable extreme.
    if config.trail_after_r is not None and r_best >= config.trail_after_r:
        trail_dist = config.trail_step_r * state.risk_distance
        if side is Side.LONG:
            candidate = state.best_favorable - trail_dist
        else:
            candidate = state.best_favorable + trail_dist
        # Never trail beyond take-profit in a way that inverts the trade.
        if side is Side.LONG:
            candidate = min(candidate, take_profit)
        else:
            candidate = max(candidate, take_profit)
        tightened = _tighten_stop(side, new_stop, candidate)
        if tightened != new_stop:
            new_stop = tightened
            notes.append("trail")

    return ManagementAction(
        new_stop=new_stop if new_stop != stop_loss else None,
        partial_price=partial_price,
        partial_size=partial_size,
        notes=tuple(notes),
    )
