"""
Offline event-driven backtest engine for Phase 1 MVP.

Consumes signals from core_strategy and simulates fills, stops, targets,
and equity risk sizing on historical OHLCV bars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from core_strategy import Side, Signal, StrategyConfig, generate_signals
from risk import RiskManager


@dataclass
class Trade:
    signal_index: int
    side: Side
    entry_time: pd.Timestamp
    entry_price: float
    stop_loss: float
    take_profit: float
    size: float
    risk_amount: float
    exit_time: Optional[pd.Timestamp] = None
    exit_price: Optional[float] = None
    exit_reason: Optional[str] = None
    pnl: float = 0.0
    return_pct: float = 0.0


@dataclass
class BacktestResult:
    trades: list[Trade] = field(default_factory=list)
    equity_curve: pd.Series = field(default_factory=pd.Series)
    metrics: dict[str, float] = field(default_factory=dict)
    annotated: pd.DataFrame = field(default_factory=pd.DataFrame)


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 10_000.0
    risk_per_trade: float = 0.01  # 1% of equity
    fee_bps: float = 0.0
    # Adverse fill model (applied on top of fees).
    slippage_bps: float = 2.0
    spread_bps: float = 2.0
    # If SL and TP both touchable on the same bar, assume stop is hit first.
    conservative_exits: bool = True
    # Circuit breakers (New York calendar day via timestamp.date()).
    daily_loss_limit: float = 0.03  # 3% of day-start equity
    max_consecutive_losses: int = 3
    enable_risk_guards: bool = True


def _position_size(equity: float, risk_pct: float, entry: float, stop: float) -> tuple[float, float]:
    risk_amount = equity * risk_pct
    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0:
        return 0.0, 0.0
    size = risk_amount / risk_per_unit
    return size, risk_amount


def _apply_fee(notional: float, fee_bps: float) -> float:
    return notional * (fee_bps / 10_000.0)


def _adverse_fill(side: Side, price: float, *, is_entry: bool, slippage_bps: float, spread_bps: float) -> float:
    """
    Worsen fills vs mid price:
      long entry / short exit  -> pay up
      short entry / long exit  -> receive less
    """
    half_spread = spread_bps / 2.0
    cost_bps = slippage_bps + half_spread
    mult = cost_bps / 10_000.0
    buy_side = (side is Side.LONG and is_entry) or (side is Side.SHORT and not is_entry)
    if buy_side:
        return price * (1.0 + mult)
    return price * (1.0 - mult)


def _exit_on_bar(
    trade: Trade,
    bar_high: float,
    bar_low: float,
    conservative: bool,
) -> Optional[tuple[float, str]]:
    hit_sl = bar_low <= trade.stop_loss if trade.side == Side.LONG else bar_high >= trade.stop_loss
    hit_tp = bar_high >= trade.take_profit if trade.side == Side.LONG else bar_low <= trade.take_profit

    if hit_sl and hit_tp:
        if conservative:
            return trade.stop_loss, "stop_loss"
        return trade.take_profit, "take_profit"
    if hit_sl:
        return trade.stop_loss, "stop_loss"
    if hit_tp:
        return trade.take_profit, "take_profit"
    return None


def compute_metrics(trades: list[Trade], equity_curve: pd.Series) -> dict[str, float]:
    if equity_curve.empty:
        return {
            "n_trades": 0.0,
            "win_rate": 0.0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
            "profit_factor": 0.0,
            "final_equity": float("nan"),
        }

    closed = [t for t in trades if t.exit_reason is not None]
    wins = [t for t in closed if t.pnl > 0]
    losses = [t for t in closed if t.pnl <= 0]
    gross_profit = float(sum(t.pnl for t in wins))
    gross_loss = float(abs(sum(t.pnl for t in losses)))

    peak = equity_curve.cummax()
    drawdown = (equity_curve - peak) / peak.replace(0, np.nan)
    max_dd = float(drawdown.min()) if len(drawdown) else 0.0
    if not np.isfinite(max_dd):
        max_dd = 0.0

    profit_factor = (
        gross_profit / gross_loss
        if gross_loss > 0
        else (float("inf") if gross_profit > 0 else 0.0)
    )

    return {
        "n_trades": float(len(closed)),
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "total_pnl": float(sum(t.pnl for t in closed)),
        # Reported as a non-negative fraction (e.g. 0.12 == 12% peak-to-trough).
        "max_drawdown": abs(max_dd),
        "profit_factor": float(profit_factor) if np.isfinite(profit_factor) else float("inf"),
        "final_equity": float(equity_curve.iloc[-1]),
        "skipped_by_risk": 0.0,
    }


class Backtester:
    """Bar-by-bar event-driven backtester."""

    def __init__(
        self,
        strategy_config: Optional[StrategyConfig] = None,
        backtest_config: Optional[BacktestConfig] = None,
    ) -> None:
        self.strategy_config = strategy_config or StrategyConfig()
        self.backtest_config = backtest_config or BacktestConfig()

    def run(self, ohlcv: pd.DataFrame) -> BacktestResult:
        annotated, signals = generate_signals(ohlcv, self.strategy_config)
        signal_map: dict[int, Signal] = {s.index: s for s in signals}

        equity = self.backtest_config.initial_equity
        equity_points: list[tuple[pd.Timestamp, float]] = []
        trades: list[Trade] = []
        open_trade: Optional[Trade] = None
        skipped_by_risk = 0

        risk_mgr: Optional[RiskManager] = None
        if self.backtest_config.enable_risk_guards:
            risk_mgr = RiskManager(
                daily_loss_limit=self.backtest_config.daily_loss_limit,
                max_consecutive_losses=self.backtest_config.max_consecutive_losses,
            )

        highs = annotated["high"].to_numpy(dtype=float)
        lows = annotated["low"].to_numpy(dtype=float)
        index = annotated.index

        for i in range(len(annotated)):
            ts = index[i]
            if risk_mgr is not None:
                risk_mgr.on_bar(ts, equity)

            # 1) Manage open position exits from the bar AFTER entry onward.
            if open_trade is not None and i > open_trade.signal_index:
                result = _exit_on_bar(
                    open_trade,
                    bar_high=float(highs[i]),
                    bar_low=float(lows[i]),
                    conservative=self.backtest_config.conservative_exits,
                )
                if result is not None:
                    raw_exit, reason = result
                    exit_price = _adverse_fill(
                        open_trade.side,
                        raw_exit,
                        is_entry=False,
                        slippage_bps=self.backtest_config.slippage_bps,
                        spread_bps=self.backtest_config.spread_bps,
                    )
                    pnl = self._realize(open_trade, exit_price)
                    open_trade.exit_time = ts
                    open_trade.exit_price = exit_price
                    open_trade.exit_reason = reason
                    open_trade.pnl = pnl
                    open_trade.return_pct = pnl / equity if equity else 0.0
                    equity += pnl
                    trades.append(open_trade)
                    if risk_mgr is not None:
                        risk_mgr.register_closed_trade(ts, equity, pnl)
                    open_trade = None

            # 2) Enter new trades only when flat, on signal bar close.
            if open_trade is None and i in signal_map:
                if risk_mgr is not None and not risk_mgr.allow_entry(ts):
                    skipped_by_risk += 1
                else:
                    sig = signal_map[i]
                    fill_entry = _adverse_fill(
                        sig.side,
                        sig.entry,
                        is_entry=True,
                        slippage_bps=self.backtest_config.slippage_bps,
                        spread_bps=self.backtest_config.spread_bps,
                    )
                    # Size from structural risk distance; fill uses adverse entry.
                    size, risk_amount = _position_size(
                        equity,
                        self.backtest_config.risk_per_trade,
                        sig.entry,
                        sig.stop_loss,
                    )
                    if size > 0:
                        fee = _apply_fee(size * fill_entry, self.backtest_config.fee_bps)
                        equity -= fee
                        open_trade = Trade(
                            signal_index=sig.index,
                            side=sig.side,
                            entry_time=ts,
                            entry_price=fill_entry,
                            stop_loss=sig.stop_loss,
                            take_profit=sig.take_profit,
                            size=size,
                            risk_amount=risk_amount,
                        )

            equity_points.append((ts, equity))

        # Mark-to-market flatten at last close if still open.
        if open_trade is not None:
            last_ts = index[-1]
            last_close = float(annotated["close"].iloc[-1])
            exit_price = _adverse_fill(
                open_trade.side,
                last_close,
                is_entry=False,
                slippage_bps=self.backtest_config.slippage_bps,
                spread_bps=self.backtest_config.spread_bps,
            )
            pnl = self._realize(open_trade, exit_price)
            open_trade.exit_time = last_ts
            open_trade.exit_price = exit_price
            open_trade.exit_reason = "eod"
            open_trade.pnl = pnl
            open_trade.return_pct = pnl / equity if equity else 0.0
            equity += pnl
            trades.append(open_trade)
            if risk_mgr is not None:
                risk_mgr.register_closed_trade(last_ts, equity, pnl)
            equity_points[-1] = (last_ts, equity)

        equity_curve = pd.Series(
            data=[e for _, e in equity_points],
            index=pd.DatetimeIndex([t for t, _ in equity_points]),
            name="equity",
        )
        metrics = compute_metrics(trades, equity_curve)
        metrics["skipped_by_risk"] = float(skipped_by_risk)
        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            annotated=annotated,
        )

    def _realize(self, trade: Trade, exit_price: float) -> float:
        direction = 1.0 if trade.side == Side.LONG else -1.0
        gross = direction * (exit_price - trade.entry_price) * trade.size
        fee = _apply_fee(trade.size * exit_price, self.backtest_config.fee_bps)
        return gross - fee
