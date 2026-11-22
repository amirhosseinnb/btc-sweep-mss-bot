"""
AJV Rulebook — executable checklist helpers (educational / research).

Mirrors docs in `javid/` and `docs/RULEBOOK.md` so the golden path and
no-trade list stay inspectable from code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from core_strategy import StrategyConfig
from scoring import ScoreBreakdown, ScoreQuality, passes_critical_gates, score_quality


GOLDEN_LONG = (
    "Sell-Side Sweep",
    "Reclaim",
    "Bullish Displacement",
    "Bullish MSS/BOS",
    "Retracement into FVG/OB",
    "R:R >= 1:2",
)

GOLDEN_SHORT = (
    "Buy-Side Sweep",
    "Reclaim",
    "Bearish Displacement",
    "Bearish MSS/BOS",
    "Retracement into FVG/OB",
    "R:R >= 1:2",
)

NO_TRADE_CONDITIONS = (
    "No clear liquidity sweep",
    "No reclaim after the sweep",
    "No meaningful displacement",
    "No MSS/BOS confirmation",
    "Setup in middle of range with no edge",
    "R:R below system requirement (< 1:2)",
    "Stop loss excessively large vs setup",
    "HTF context strongly contradicts without reversal structure",
    "Price already extended — chase entry",
    "Setup too ambiguous to check objectively",
    "Score 0-11 (No Trade band)",
    "Score 12-15 Weak when reject_weak_scores is ON",
)

EXECUTION_CHECKLIST = (
    "What is the HTF bias?",
    "Where is the nearest meaningful liquidity?",
    "What is the CRT range?",
    "Which side was swept?",
    "Was there a reclaim?",
    "Is divergence present?",
    "Was there displacement?",
    "Did MSS/BOS occur?",
    "Where is the FVG/OB retracement zone?",
    "Where is the structural invalidation?",
    "Where is the liquidity-based target?",
    "Is R:R at least 1:2?",
)


@dataclass(frozen=True)
class RulebookGateReport:
    ok: bool
    missing: tuple[str, ...]
    quality: Optional[str]
    notes: tuple[str, ...]


def javid_strategy_config() -> StrategyConfig:
    """Canonical config for the AJV Rulebook preset (golden path gates)."""
    return StrategyConfig(
        require_htf_bias=True,
        require_session=True,
        session_mode="london_ny",
        require_crt_sweep=True,
        require_crt_reclaim=True,
        require_displacement=True,
        require_divergence=True,
        accept_hidden_divergence=True,
        enable_scoring=True,
        reject_weak_scores=True,
        min_score=16,
        # Evidence on 4y BTC 4H: R:R 2.5 improves PF/PnL vs 2.0 without cutting trades.
        risk_reward=2.5,
        tp_mode="liquidity",
        entry_mode="mss_close",
    )


def javid_backtest_config(equity: float = 10_000.0):
    """Paper-discipline backtest knobs for the Rulebook preset."""
    from backtester import BacktestConfig
    from trade_management import TradeManageConfig

    return BacktestConfig(
        initial_equity=equity,
        risk_per_trade=0.01,
        fee_bps=4.0,
        slippage_bps=2.0,
        spread_bps=2.0,
        enable_risk_guards=True,
        max_trades_per_day=1,
        cooldown_bars_after_loss=2,
        trade_manage=TradeManageConfig(enable=True),
    )


def evaluate_score_gates(
    breakdown: ScoreBreakdown,
    *,
    min_score: int = 16,
    reject_weak: bool = True,
) -> RulebookGateReport:
    missing: list[str] = []
    notes: list[str] = []
    if not passes_critical_gates(
        breakdown,
        require_reclaim=True,
        require_displacement=True,
        require_divergence=True,
    ):
        if breakdown.sweep < 1:
            missing.append("Liquidity Sweep")
        if breakdown.mss < 1:
            missing.append("MSS/BOS")
        if breakdown.risk_reward < 1:
            missing.append("R:R >= 1:2")
        if breakdown.reclaim < 1:
            missing.append("Reclaim required")
        if breakdown.displacement < 1:
            missing.append("Displacement required")
        if breakdown.divergence < 1:
            missing.append("Divergence required")
    quality = score_quality(breakdown.total)
    if quality is ScoreQuality.NO_TRADE:
        missing.append("Score 0-11 No Trade band")
    if reject_weak and quality is ScoreQuality.WEAK:
        missing.append("Score 12-15 Weak rejected")
    if breakdown.total < min_score:
        missing.append(f"Score < min_score ({min_score})")
    if breakdown.reclaim < 1:
        notes.append("Reclaim missing — ideal CRT path incomplete")
    if breakdown.displacement < 1:
        notes.append("Displacement weak/missing")
    if breakdown.divergence < 1:
        notes.append("No divergence confirmation")
    return RulebookGateReport(
        ok=not missing,
        missing=tuple(missing),
        quality=quality.value,
        notes=tuple(notes),
    )
