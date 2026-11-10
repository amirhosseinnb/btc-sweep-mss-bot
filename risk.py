"""
Risk controls for Phase 1.8: daily loss limit + consecutive-loss lockout.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import pandas as pd


@dataclass
class RiskState:
    day: Optional[date] = None
    day_start_equity: float = 0.0
    locked_until_day: Optional[date] = None
    consecutive_losses: int = 0
    halted: bool = False
    halt_reason: Optional[str] = None


class RiskManager:
    """
    Circuit breakers evaluated on New York calendar dates (index.date).

    - daily_loss_limit: fraction of day-start equity (e.g. 0.03 = 3%)
    - max_consecutive_losses: stop new entries after N losers in a row
    """

    def __init__(
        self,
        *,
        daily_loss_limit: float = 0.03,
        max_consecutive_losses: int = 3,
    ) -> None:
        if daily_loss_limit <= 0 or daily_loss_limit > 1:
            raise ValueError("daily_loss_limit must be in (0, 1]")
        if max_consecutive_losses < 1:
            raise ValueError("max_consecutive_losses must be >= 1")
        self.daily_loss_limit = float(daily_loss_limit)
        self.max_consecutive_losses = int(max_consecutive_losses)
        self.state = RiskState()

    def on_bar(self, ts: pd.Timestamp, equity: float) -> None:
        d = ts.date()
        if self.state.day != d:
            self.state.day = d
            self.state.day_start_equity = equity
            # Unlock if lockout day has passed.
            if self.state.locked_until_day is not None and d >= self.state.locked_until_day:
                self.state.locked_until_day = None
                if self.state.halt_reason == "daily_loss_limit":
                    self.state.halted = False
                    self.state.halt_reason = None
            # Soft-reset consecutive-loss halt on each new NY day.
            if self.state.halt_reason == "consecutive_losses":
                self.state.halted = False
                self.state.halt_reason = None
                self.state.consecutive_losses = 0

    def allow_entry(self, ts: pd.Timestamp) -> bool:
        d = ts.date()
        if self.state.halted and self.state.halt_reason == "consecutive_losses":
            return False
        if self.state.locked_until_day is not None and d < self.state.locked_until_day:
            return False
        return True

    def register_closed_trade(self, ts: pd.Timestamp, equity_after: float, pnl: float) -> None:
        d = ts.date()
        if pnl < 0:
            self.state.consecutive_losses += 1
        elif pnl > 0:
            self.state.consecutive_losses = 0

        if self.state.consecutive_losses >= self.max_consecutive_losses:
            self.state.halted = True
            self.state.halt_reason = "consecutive_losses"

        start = self.state.day_start_equity or equity_after
        if start > 0:
            day_pnl_frac = (equity_after - start) / start
            if day_pnl_frac <= -self.daily_loss_limit:
                self.state.halted = True
                self.state.halt_reason = "daily_loss_limit"
                # Lock for the remainder of today; next calendar day unlocks in on_bar.
                self.state.locked_until_day = d + timedelta(days=1)
