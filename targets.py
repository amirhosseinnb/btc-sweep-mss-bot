"""
Take-profit / liquidity-target helpers (Javid Rulebook §6–7, §12).

Priority options:
  - opposite swing liquidity (Buy-side for longs / Sell-side for shorts)
  - CRT midpoint / opposite CRT boundary
  - fixed R:R fallback (always enforced >= 2)
"""

from __future__ import annotations

from typing import Optional

import numpy as np

from core_strategy import Side, SwingPoint


def realized_rr(side: Side, entry: float, stop: float, take_profit: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        return 0.0
    if side is Side.LONG:
        reward = take_profit - entry
    else:
        reward = entry - take_profit
    if reward <= 0:
        return 0.0
    return float(reward / risk)


def fixed_rr_target(side: Side, entry: float, stop: float, rr: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError("entry and stop must differ")
    if rr < 2.0:
        raise ValueError("Phase-1 / Rulebook requires risk_reward >= 2.0")
    if side is Side.LONG:
        if not (stop < entry):
            raise ValueError("long requires stop < entry")
        return entry + rr * risk
    if not (stop > entry):
        raise ValueError("short requires stop > entry")
    return entry - rr * risk


def find_liquidity_target(
    swings: list[SwingPoint],
    *,
    side: Side,
    asof_index: int,
    entry: float,
    stop: float,
    min_rr: float = 2.0,
) -> Optional[float]:
    """
    Nearest confirmed opposite-side swing that still yields R:R >= min_rr.

    Long  -> Buy-side liquidity (prior swing highs above entry)
    Short -> Sell-side liquidity (prior swing lows below entry)
    """
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    candidates: list[tuple[float, float]] = []
    for sw in swings:
        if sw.confirmed_at > asof_index or sw.index > asof_index:
            continue
        if side is Side.LONG and sw.kind == "high" and sw.price > entry:
            rr = (sw.price - entry) / risk
            if rr + 1e-12 >= min_rr:
                candidates.append((float(sw.price), rr))
        elif side is Side.SHORT and sw.kind == "low" and sw.price < entry:
            rr = (entry - sw.price) / risk
            if rr + 1e-12 >= min_rr:
                candidates.append((float(sw.price), rr))

    if not candidates:
        return None
    # Prefer nearest objective (less extension / chase).
    candidates.sort(key=lambda x: abs(x[0] - entry))
    return candidates[0][0]


def find_crt_target(
    *,
    side: Side,
    entry: float,
    stop: float,
    crt_high: float,
    crt_low: float,
    min_rr: float = 2.0,
) -> Optional[float]:
    """
    CRT objective: midpoint first, then opposite boundary, if R:R holds.
    """
    if not (np.isfinite(crt_high) and np.isfinite(crt_low)) or crt_high <= crt_low:
        return None
    risk = abs(entry - stop)
    if risk <= 0:
        return None

    mid = 0.5 * (crt_high + crt_low)
    if side is Side.LONG:
        ordered = [mid, float(crt_high)]
        for tp in ordered:
            if tp > entry and (tp - entry) / risk + 1e-12 >= min_rr:
                return tp
    else:
        ordered = [mid, float(crt_low)]
        for tp in ordered:
            if tp < entry and (entry - tp) / risk + 1e-12 >= min_rr:
                return tp
    return None


def resolve_take_profit(
    *,
    side: Side,
    entry: float,
    stop: float,
    risk_reward: float,
    tp_mode: str,
    swings: list[SwingPoint],
    asof_index: int,
    crt_high: float,
    crt_low: float,
) -> tuple[float, bool, str]:
    """
    Returns (take_profit, used_liquidity_or_crt_objective, reason).

    Always enforces R:R >= risk_reward (and therefore >= 2 via StrategyConfig).
    """
    fallback = fixed_rr_target(side, entry, stop, risk_reward)

    if tp_mode == "fixed_rr":
        return fallback, False, "fixed_rr"

    if tp_mode == "liquidity":
        liq = find_liquidity_target(
            swings,
            side=side,
            asof_index=asof_index,
            entry=entry,
            stop=stop,
            min_rr=risk_reward,
        )
        if liq is not None:
            return liq, True, "liquidity_swing"
        return fallback, False, "fixed_rr_fallback"

    if tp_mode == "crt_opposite":
        crt_tp = find_crt_target(
            side=side,
            entry=entry,
            stop=stop,
            crt_high=crt_high,
            crt_low=crt_low,
            min_rr=risk_reward,
        )
        if crt_tp is not None:
            return crt_tp, True, "crt_boundary"
        liq = find_liquidity_target(
            swings,
            side=side,
            asof_index=asof_index,
            entry=entry,
            stop=stop,
            min_rr=risk_reward,
        )
        if liq is not None:
            return liq, True, "liquidity_swing"
        return fallback, False, "fixed_rr_fallback"

    raise ValueError(f"Unknown tp_mode: {tp_mode}")
