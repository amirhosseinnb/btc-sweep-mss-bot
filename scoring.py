"""
24-point confluence scoring for Phase 1 setups.

Categories (max 24):
  Liquidity Sweep     0-4
  Market Structure    0-4
  HTF Bias            0-3
  Session             0-3
  CRT                 0-3
  Divergence          0-3
  ICT Zone (FVG/OB/OTE/PD) 0-2
  Timing                    0-2
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from core_strategy import Side

MAX_SCORE = 24


@dataclass(frozen=True)
class ScoreBreakdown:
    sweep: int
    structure: int
    htf: int
    session: int
    crt: int
    divergence: int
    fvg: int  # ICT zone bucket: FVG / OB / OTE / PD
    timing: int

    @property
    def total(self) -> int:
        return (
            self.sweep
            + self.structure
            + self.htf
            + self.session
            + self.crt
            + self.divergence
            + self.fvg
            + self.timing
        )

    def as_dict(self) -> dict[str, int]:
        return {
            "sweep": self.sweep,
            "structure": self.structure,
            "htf": self.htf,
            "session": self.session,
            "crt": self.crt,
            "divergence": self.divergence,
            "ict_zone": self.fvg,
            "timing": self.timing,
            "total": self.total,
        }


@dataclass(frozen=True)
class SetupScoreContext:
    side: Side
    sweep_index: int
    mss_index: int
    atr_at_sweep: float
    sweep_penetration: float
    mss_body: float
    atr_at_mss: float
    htf_bias: int  # +1 bull, -1 bear, 0 flat
    in_london_ny: bool
    in_killzone: bool
    crt_swept: bool
    crt_reclaimed: bool
    divergence_ok: bool
    fvg_present: bool
    order_block_present: bool = False
    ote_aligned: bool = False
    pd_aligned: bool = False
    displacement_atr_mult: float = 1.5
    choch_aligned: bool = False


def score_setup(ctx: SetupScoreContext) -> ScoreBreakdown:
    """Score a completed Sweep -> MSS setup against the 24-point rubric."""

    # --- Liquidity Sweep (0-4) ---
    sweep = 2  # base: valid sweep exists
    if np.isfinite(ctx.atr_at_sweep) and ctx.atr_at_sweep > 0:
        ratio = ctx.sweep_penetration / ctx.atr_at_sweep
        if ratio >= 0.25:
            sweep += 1
        if ratio >= 0.50:
            sweep += 1
    sweep = min(4, sweep)

    # --- Market Structure / MSS (0-4) ---
    structure = 2  # base: MSS confirmed
    if ctx.choch_aligned:
        structure += 1
    if np.isfinite(ctx.atr_at_mss) and ctx.atr_at_mss > 0:
        body_r = ctx.mss_body / ctx.atr_at_mss
        if body_r >= 1.0:
            structure += 1
        if body_r >= ctx.displacement_atr_mult and structure < 4:
            structure += 1
    structure = min(4, structure)

    # --- HTF Bias (0-3) ---
    if ctx.side is Side.LONG:
        if ctx.htf_bias > 0:
            htf = 3
        elif ctx.htf_bias == 0:
            htf = 1
        else:
            htf = 0
    else:
        if ctx.htf_bias < 0:
            htf = 3
        elif ctx.htf_bias == 0:
            htf = 1
        else:
            htf = 0

    # --- Session (0-3) ---
    if ctx.in_killzone:
        session = 3
    elif ctx.in_london_ny:
        session = 2
    else:
        session = 0

    # --- CRT (0-3) ---
    crt = 0
    if ctx.crt_swept:
        crt += 1
    if ctx.crt_reclaimed:
        crt += 2
    crt = min(3, crt)

    # --- Divergence (0-3) ---
    divergence = 3 if ctx.divergence_ok else 0

    # --- ICT zone / Entry quality (0-2) ---
    # 1 point for any micro-zone (FVG or OB), +1 for OTE or PD alignment.
    zone_hit = ctx.fvg_present or ctx.order_block_present
    location_hit = ctx.ote_aligned or ctx.pd_aligned
    if zone_hit and location_hit:
        fvg = 2
    elif zone_hit or location_hit:
        fvg = 1
    else:
        fvg = 0

    # --- Timing (0-2) ---
    lag = ctx.mss_index - ctx.sweep_index
    if lag <= 5:
        timing = 2
    elif lag <= 10:
        timing = 1
    else:
        timing = 0

    return ScoreBreakdown(
        sweep=sweep,
        structure=structure,
        htf=htf,
        session=session,
        crt=crt,
        divergence=divergence,
        fvg=fvg,
        timing=timing,
    )


def passes_min_score(breakdown: ScoreBreakdown, min_score: int) -> bool:
    if min_score < 0 or min_score > MAX_SCORE:
        raise ValueError(f"min_score must be in [0, {MAX_SCORE}]")
    return breakdown.total >= min_score


def format_score(breakdown: ScoreBreakdown) -> str:
    parts = [
        f"sw{breakdown.sweep}",
        f"st{breakdown.structure}",
        f"htf{breakdown.htf}",
        f"ses{breakdown.session}",
        f"crt{breakdown.crt}",
        f"div{breakdown.divergence}",
        f"fvg{breakdown.fvg}",
        f"t{breakdown.timing}",
    ]
    return f"{breakdown.total}/{MAX_SCORE}(" + "|".join(parts) + ")"
