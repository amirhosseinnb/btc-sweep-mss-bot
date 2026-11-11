"""
AJV Trading Philosophy — executable principles for Phase 1.

These are not marketing copy: helpers validate that strategy/backtest
configs still obey the project's non-negotiable rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from backtester import BacktestConfig
from core_strategy import StrategyConfig

PHASE = "Phase 1 — Research / Paper only"

PRINCIPLES_FA = (
    "معامله فقط با قانون؛ نه احساس و نه پیش‌بینی خبر.",
    "اول بقا، بعد سود: ریسک هر معامله حداکثر ۱٪ و حداقل R:R برابر ۲.",
    "بدون confluence کافی وارد نشو؛ سیگنال ضعیف را رد کن.",
    "اگر شرایط No-Trade فعال است، هیچ ورود جدیدی مجاز نیست.",
    "تا پایان فاز ۱ هیچ سفارش واقعی به صرافی ارسال نمی‌شود.",
    "هر تغییر قانون باید با بک‌تست و Walk-Forward سنجیده شود.",
)

PRINCIPLES_EN = (
    "Rules over emotion: every entry must map to coded conditions.",
    "Survival first: max 1% risk per trade and minimum 2R reward.",
    "No weak setups: confluence/score gates beat FOMO.",
    "No-Trade means no-trade — circuit breakers win.",
    "Phase 1 is read-only / paper; live orders are forbidden.",
    "Change the rules only after offline validation.",
)


@dataclass(frozen=True)
class PhilosophyReport:
    ok: bool
    violations: tuple[str, ...]
    notes: tuple[str, ...]


def check_philosophy(
    strategy: Optional[StrategyConfig] = None,
    backtest: Optional[BacktestConfig] = None,
    *,
    orders_enabled: bool = False,
) -> PhilosophyReport:
    """Return compliance report for current configs."""
    violations: list[str] = []
    notes: list[str] = []

    if orders_enabled:
        violations.append("orders_enabled=True violates Phase-1 read-only philosophy")

    if strategy is not None:
        if strategy.risk_reward < 2.0:
            violations.append("risk_reward < 2.0")
        if strategy.enable_scoring and strategy.min_score <= 0:
            notes.append("scoring enabled but min_score is 0 (no filter effect)")
        if strategy.require_session:
            notes.append("session filter ON — aligns with killzone philosophy")
        if strategy.require_htf_bias:
            notes.append("HTF bias ON — aligns with higher-timeframe philosophy")

    if backtest is not None:
        if backtest.risk_per_trade > 0.01 + 1e-12:
            violations.append("risk_per_trade > 1%")
        if backtest.risk_per_trade <= 0:
            violations.append("risk_per_trade must be > 0")
        if not backtest.enable_risk_guards:
            notes.append("risk guards OFF — weaker adherence to survival principle")
        if backtest.trade_manage.enable:
            notes.append("trade management ON — aligns with active trade care")

    return PhilosophyReport(
        ok=not violations,
        violations=tuple(violations),
        notes=tuple(notes),
    )


def philosophy_markdown() -> str:
    lines = [
        f"# AJV Trading Philosophy ({PHASE})",
        "",
        "## اصول فارسی",
        "",
    ]
    for i, p in enumerate(PRINCIPLES_FA, 1):
        lines.append(f"{i}. {p}")
    lines.extend(["", "## Principles (EN)", ""])
    for i, p in enumerate(PRINCIPLES_EN, 1):
        lines.append(f"{i}. {p}")
    lines.extend(
        [
            "",
            "## Enforcement in code",
            "",
            "- `StrategyConfig.risk_reward >= 2.0`",
            "- `BacktestConfig.risk_per_trade` default `0.01`",
            "- `paper_trader` / live site: `orders_enabled=false`",
            "- `check_philosophy()` validates configs before research runs",
            "",
        ]
    )
    return "\n".join(lines)
