"""
AJV Rulebook 24-point confluence scoring (12 categories × 0–2).

Categories (max 24):
  HTF Bias            0-2
  Market Structure    0-2
  Key Zone            0-2
  CRT Range           0-2
  Liquidity Sweep     0-2
  Divergence          0-2
  Reclaim             0-2
  Displacement        0-2
  MSS/BOS             0-2
  FVG / Order Block   0-2
  Liquidity Target    0-2
  Risk-to-Reward      0-2

Decision bands:
  0-11  No Trade
  12-15 Weak
  16-18 Review
  19-21 Good
  22-24 A+

Critical minimum (never overridden by a high total):
  Liquidity Sweep + MSS/BOS + R:R >= 1:2
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from core_strategy import Side

MAX_SCORE = 24


class ScoreQuality(str, Enum):
    NO_TRADE = "no_trade"
    WEAK = "weak"
    REVIEW = "review"
    GOOD = "good"
    A_PLUS = "a_plus"


@dataclass(frozen=True)
class ScoreBreakdown:
    htf: int
    market_structure: int
    key_zone: int
    crt: int
    sweep: int
    divergence: int
    reclaim: int
    displacement: int
    mss: int
    fvg_ob: int
    liquidity_target: int
    risk_reward: int

    @property
    def total(self) -> int:
        return (
            self.htf
            + self.market_structure
            + self.key_zone
            + self.crt
            + self.sweep
            + self.divergence
            + self.reclaim
            + self.displacement
            + self.mss
            + self.fvg_ob
            + self.liquidity_target
            + self.risk_reward
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "htf": self.htf,
            "market_structure": self.market_structure,
            "key_zone": self.key_zone,
            "crt": self.crt,
            "sweep": self.sweep,
            "divergence": self.divergence,
            "reclaim": self.reclaim,
            "displacement": self.displacement,
            "mss": self.mss,
            "fvg_ob": self.fvg_ob,
            "liquidity_target": self.liquidity_target,
            "risk_reward": self.risk_reward,
            "total": self.total,
        }


@dataclass(frozen=True)
class SetupScoreContext:
    """Inputs for one completed Sweep → (Reclaim) → MSS setup."""

    side: Side
    sweep_index: int
    mss_index: int
    atr_at_sweep: float
    sweep_penetration: float
    mss_body: float
    atr_at_mss: float
    htf_bias: int  # +1 bull, -1 bear, 0 flat
    crt_levels_valid: bool
    crt_swept: bool
    crt_reclaimed: bool
    divergence_regular: bool
    divergence_hidden: bool = False
    fvg_present: bool = False
    order_block_present: bool = False
    ote_aligned: bool = False
    pd_aligned: bool = False
    choch_aligned: bool = False
    bos_aligned: bool = False
    displacement_atr_mult: float = 1.5
    realized_rr: float = 2.0
    liquidity_target_used: bool = False
    mss_confirmed: bool = True


def score_quality(total: int) -> ScoreQuality:
    if total <= 11:
        return ScoreQuality.NO_TRADE
    if total <= 15:
        return ScoreQuality.WEAK
    if total <= 18:
        return ScoreQuality.REVIEW
    if total <= 21:
        return ScoreQuality.GOOD
    return ScoreQuality.A_PLUS


def passes_critical_gates(
    breakdown: ScoreBreakdown,
    *,
    require_reclaim: bool = False,
    require_displacement: bool = False,
    require_divergence: bool = False,
) -> bool:
    """Rulebook golden floor: Sweep + MSS/BOS + R:R >= 1:2 (+ optional hardenings)."""
    if not (breakdown.sweep >= 1 and breakdown.mss >= 1 and breakdown.risk_reward >= 1):
        return False
    if require_reclaim and breakdown.reclaim < 1:
        return False
    if require_displacement and breakdown.displacement < 1:
        return False
    if require_divergence and breakdown.divergence < 1:
        return False
    return True


def score_setup(ctx: SetupScoreContext) -> ScoreBreakdown:
    """Score a setup against the Javid 12×0–2 rubric."""

    # --- HTF Bias (0-2) ---
    if ctx.side is Side.LONG:
        if ctx.htf_bias > 0:
            htf = 2
        elif ctx.htf_bias == 0:
            htf = 1
        else:
            htf = 0
    else:
        if ctx.htf_bias < 0:
            htf = 2
        elif ctx.htf_bias == 0:
            htf = 1
        else:
            htf = 0

    # --- Market Structure (0-2): clarity of trend / CHOCH context ---
    if ctx.choch_aligned:
        market_structure = 2
    elif ctx.bos_aligned or ctx.htf_bias != 0:
        market_structure = 1
    else:
        market_structure = 0

    # --- Key Zone (0-2): Premium/Discount / OTE ---
    if ctx.pd_aligned and ctx.ote_aligned:
        key_zone = 2
    elif ctx.pd_aligned or ctx.ote_aligned:
        key_zone = 1
    else:
        key_zone = 0

    # --- CRT Range (0-2) ---
    if ctx.crt_levels_valid and ctx.crt_swept and ctx.crt_reclaimed:
        crt = 2
    elif ctx.crt_levels_valid and (ctx.crt_swept or ctx.crt_reclaimed):
        crt = 1
    else:
        crt = 0

    # --- Liquidity Sweep (0-2) ---
    sweep = 1  # setup only exists after a valid sweep
    if np.isfinite(ctx.atr_at_sweep) and ctx.atr_at_sweep > 0:
        ratio = ctx.sweep_penetration / ctx.atr_at_sweep
        if ratio >= 0.35:
            sweep = 2
    sweep = min(2, sweep)

    # --- Divergence (0-2): regular preferred; hidden weaker ---
    if ctx.divergence_regular:
        divergence = 2
    elif ctx.divergence_hidden:
        divergence = 1
    else:
        divergence = 0

    # --- Reclaim (0-2) ---
    reclaim = 2 if ctx.crt_reclaimed else 0

    # --- Displacement (0-2) ---
    displacement = 0
    if np.isfinite(ctx.atr_at_mss) and ctx.atr_at_mss > 0:
        body_r = ctx.mss_body / ctx.atr_at_mss
        if body_r >= ctx.displacement_atr_mult:
            displacement = 2
        elif body_r >= 1.0:
            displacement = 1

    # --- MSS/BOS (0-2) ---
    if ctx.mss_confirmed:
        mss = 2 if ctx.choch_aligned or ctx.bos_aligned else 1
        # Strong body on MSS candle upgrades to full marks.
        if (
            np.isfinite(ctx.atr_at_mss)
            and ctx.atr_at_mss > 0
            and (ctx.mss_body / ctx.atr_at_mss) >= 1.0
        ):
            mss = 2
    else:
        mss = 0

    # --- FVG / Order Block (0-2) ---
    if ctx.fvg_present and ctx.order_block_present:
        fvg_ob = 2
    elif ctx.fvg_present or ctx.order_block_present:
        fvg_ob = 1
    else:
        fvg_ob = 0

    # --- Liquidity Target (0-2) ---
    if ctx.liquidity_target_used and ctx.realized_rr >= 2.5:
        liquidity_target = 2
    elif ctx.liquidity_target_used and ctx.realized_rr >= 2.0:
        liquidity_target = 1
    elif ctx.realized_rr >= 2.0:
        liquidity_target = 1  # fixed-R target still counts as acceptable objective
    else:
        liquidity_target = 0

    # --- Risk-to-Reward (0-2) ---
    if ctx.realized_rr >= 2.5:
        risk_reward = 2
    elif ctx.realized_rr >= 2.0 - 1e-12:
        risk_reward = 1
    else:
        risk_reward = 0

    return ScoreBreakdown(
        htf=htf,
        market_structure=market_structure,
        key_zone=key_zone,
        crt=crt,
        sweep=sweep,
        divergence=divergence,
        reclaim=reclaim,
        displacement=displacement,
        mss=mss,
        fvg_ob=fvg_ob,
        liquidity_target=liquidity_target,
        risk_reward=risk_reward,
    )


def passes_min_score(
    breakdown: ScoreBreakdown,
    min_score: int,
    *,
    reject_weak: bool = False,
    require_reclaim: bool = False,
    require_displacement: bool = False,
    require_divergence: bool = False,
) -> bool:
    if min_score < 0 or min_score > MAX_SCORE:
        raise ValueError(f"min_score must be in [0, {MAX_SCORE}]")
    if not passes_critical_gates(
        breakdown,
        require_reclaim=require_reclaim,
        require_displacement=require_displacement,
        require_divergence=require_divergence,
    ):
        return False
    quality = score_quality(breakdown.total)
    if quality is ScoreQuality.NO_TRADE:
        return False
    if reject_weak and quality is ScoreQuality.WEAK:
        return False
    return breakdown.total >= min_score


def format_score(breakdown: ScoreBreakdown) -> str:
    q = score_quality(breakdown.total).value
    parts = [
        f"htf{breakdown.htf}",
        f"ms{breakdown.market_structure}",
        f"kz{breakdown.key_zone}",
        f"crt{breakdown.crt}",
        f"sw{breakdown.sweep}",
        f"div{breakdown.divergence}",
        f"rc{breakdown.reclaim}",
        f"dp{breakdown.displacement}",
        f"mss{breakdown.mss}",
        f"zo{breakdown.fvg_ob}",
        f"lt{breakdown.liquidity_target}",
        f"rr{breakdown.risk_reward}",
    ]
    return f"{breakdown.total}/{MAX_SCORE}:{q}(" + "|".join(parts) + ")"


def quality_label_fa(quality: ScoreQuality) -> str:
    return {
        ScoreQuality.NO_TRADE: "بدون معامله",
        ScoreQuality.WEAK: "ضعیف",
        ScoreQuality.REVIEW: "متوسط / بررسی",
        ScoreQuality.GOOD: "خوب",
        ScoreQuality.A_PLUS: "عالی A+",
    }[quality]
