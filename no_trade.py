"""
Explicit No-Trade gate for Phase 1.

Centralizes reasons to skip a new entry beyond strategy signal filters:
daily trade cap, post-loss cooldown, and optional risk circuit breakers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd

from risk import RiskManager


@dataclass(frozen=True)
class NoTradeConfig:
    """Extra no-trade rules evaluated at entry time."""

    max_trades_per_day: Optional[int] = None  # None = unlimited
    cooldown_bars_after_loss: int = 0  # 0 = off


@dataclass
class NoTradeState:
    day: Optional[date] = None
    trades_today: int = 0
    cooldown_until_bar: Optional[int] = None
    skip_counts: dict[str, int] = field(default_factory=dict)


class NoTradeGate:
    """
    Returns (allowed, reason). reason is None when entry is allowed.

    Known reasons:
      - daily_loss_limit / consecutive_losses / locked_day  (from RiskManager)
      - max_trades_per_day
      - cooldown_after_loss
    """

    def __init__(
        self,
        config: Optional[NoTradeConfig] = None,
        risk_mgr: Optional[RiskManager] = None,
    ) -> None:
        self.config = config or NoTradeConfig()
        if (
            self.config.max_trades_per_day is not None
            and self.config.max_trades_per_day < 1
        ):
            raise ValueError("max_trades_per_day must be >= 1 or None")
        if self.config.cooldown_bars_after_loss < 0:
            raise ValueError("cooldown_bars_after_loss must be >= 0")
        self.risk_mgr = risk_mgr
        self.state = NoTradeState()

    def _bump(self, reason: str) -> None:
        self.state.skip_counts[reason] = self.state.skip_counts.get(reason, 0) + 1

    def on_bar(self, ts: pd.Timestamp, equity: float) -> None:
        if self.risk_mgr is not None:
            self.risk_mgr.on_bar(ts, equity)
        d = ts.date()
        if self.state.day != d:
            self.state.day = d
            self.state.trades_today = 0

    def allow_entry(self, ts: pd.Timestamp, bar_index: int) -> tuple[bool, Optional[str]]:
        if self.risk_mgr is not None and not self.risk_mgr.allow_entry(ts):
            reason = self.risk_mgr.state.halt_reason or "risk_lock"
            if (
                self.risk_mgr.state.locked_until_day is not None
                and ts.date() < self.risk_mgr.state.locked_until_day
                and reason != "daily_loss_limit"
            ):
                reason = "locked_day"
            self._bump(reason)
            return False, reason

        max_n = self.config.max_trades_per_day
        if max_n is not None and self.state.trades_today >= max_n:
            self._bump("max_trades_per_day")
            return False, "max_trades_per_day"

        cool = self.state.cooldown_until_bar
        if cool is not None and bar_index < cool:
            self._bump("cooldown_after_loss")
            return False, "cooldown_after_loss"

        return True, None

    def register_entry(self, ts: pd.Timestamp) -> None:
        d = ts.date()
        if self.state.day != d:
            self.state.day = d
            self.state.trades_today = 0
        self.state.trades_today += 1

    def register_closed_trade(
        self,
        ts: pd.Timestamp,
        equity_after: float,
        pnl: float,
        bar_index: int,
    ) -> None:
        if self.risk_mgr is not None:
            self.risk_mgr.register_closed_trade(ts, equity_after, pnl)
        if pnl < 0 and self.config.cooldown_bars_after_loss > 0:
            self.state.cooldown_until_bar = bar_index + self.config.cooldown_bars_after_loss
