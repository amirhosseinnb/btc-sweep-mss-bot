"""
Offline event-driven backtest engine for Phase 1 MVP.

Consumes signals from core_strategy and simulates fills, stops, targets,
equity risk sizing, no-trade gates, and optional in-trade management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from core_strategy import Side, Signal, StrategyConfig, generate_signals
from no_trade import NoTradeConfig, NoTradeGate
from risk import RiskManager
from trade_management import TradeManageConfig, initial_state, manage_open_trade


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
    # Management bookkeeping
    initial_stop: Optional[float] = None
    original_size: Optional[float] = None
    partial_pnl: float = 0.0
    management_notes: str = ""


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
    # Explicit no-trade extras (on top of risk guards).
    max_trades_per_day: Optional[int] = None
    cooldown_bars_after_loss: int = 0
    # In-trade management (off by default).
    trade_manage: TradeManageConfig = field(default_factory=TradeManageConfig)


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
        "skipped_by_no_trade": 0.0,
        "partial_exits": float(sum(1 for t in closed if t.partial_pnl != 0.0)),
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
        manage_state = None
        skipped_by_risk = 0
        skipped_by_no_trade = 0

        risk_mgr: Optional[RiskManager] = None
        if self.backtest_config.enable_risk_guards:
            risk_mgr = RiskManager(
                daily_loss_limit=self.backtest_config.daily_loss_limit,
                max_consecutive_losses=self.backtest_config.max_consecutive_losses,
            )
        gate = NoTradeGate(
            NoTradeConfig(
                max_trades_per_day=self.backtest_config.max_trades_per_day,
                cooldown_bars_after_loss=self.backtest_config.cooldown_bars_after_loss,
            ),
            risk_mgr=risk_mgr,
        )
        manage_cfg = self.backtest_config.trade_manage

        highs = annotated["high"].to_numpy(dtype=float)
        lows = annotated["low"].to_numpy(dtype=float)
        index = annotated.index

        for i in range(len(annotated)):
            ts = index[i]
            gate.on_bar(ts, equity)
            bar_high = float(highs[i])
            bar_low = float(lows[i])

            # 1) Manage open position from the bar AFTER entry onward.
            # Conservative order: evaluate exits with the stop inherited from
            # prior bars, then tighten management for subsequent bars.
            if open_trade is not None and i > open_trade.signal_index:
                result = _exit_on_bar(
                    open_trade,
                    bar_high=bar_high,
                    bar_low=bar_low,
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
                    remainder_pnl = self._realize(open_trade, exit_price)
                    total_pnl = open_trade.partial_pnl + remainder_pnl
                    open_trade.exit_time = ts
                    open_trade.exit_price = exit_price
                    open_trade.exit_reason = reason
                    open_trade.pnl = total_pnl
                    open_trade.return_pct = total_pnl / equity if equity else 0.0
                    equity += remainder_pnl
                    trades.append(open_trade)
                    gate.register_closed_trade(ts, equity, total_pnl, i)
                    open_trade = None
                    manage_state = None
                elif manage_cfg.enable and manage_state is not None:
                    action = manage_open_trade(
                        side=open_trade.side,
                        entry=open_trade.entry_price,
                        stop_loss=open_trade.stop_loss,
                        take_profit=open_trade.take_profit,
                        bar_high=bar_high,
                        bar_low=bar_low,
                        state=manage_state,
                        config=manage_cfg,
                    )
                    if action.new_stop is not None:
                        open_trade.stop_loss = action.new_stop
                    if action.partial_price is not None and action.partial_size is not None:
                        fill = _adverse_fill(
                            open_trade.side,
                            action.partial_price,
                            is_entry=False,
                            slippage_bps=self.backtest_config.slippage_bps,
                            spread_bps=self.backtest_config.spread_bps,
                        )
                        part_pnl = self._realize_size(open_trade, fill, action.partial_size)
                        open_trade.partial_pnl += part_pnl
                        open_trade.size = manage_state.remaining_size
                        equity += part_pnl
                    if action.notes:
                        notes = list(
                            filter(
                                None,
                                (open_trade.management_notes, *action.notes),
                            )
                        )
                        open_trade.management_notes = ",".join(dict.fromkeys(notes))

            # 2) Enter new trades only when flat, on signal bar close.
            if open_trade is None and i in signal_map:
                allowed, reason = gate.allow_entry(ts, i)
                if not allowed:
                    if reason in {
                        "daily_loss_limit",
                        "consecutive_losses",
                        "locked_day",
                        "risk_lock",
                    }:
                        skipped_by_risk += 1
                    else:
                        skipped_by_no_trade += 1
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
                            initial_stop=sig.stop_loss,
                            original_size=size,
                        )
                        if manage_cfg.enable:
                            # Management R is measured from adverse entry fill vs structural stop.
                            manage_state = initial_state(
                                open_trade.side,
                                open_trade.entry_price,
                                open_trade.stop_loss,
                                open_trade.size,
                            )
                        gate.register_entry(ts)

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
            remainder_pnl = self._realize(open_trade, exit_price)
            total_pnl = open_trade.partial_pnl + remainder_pnl
            open_trade.exit_time = last_ts
            open_trade.exit_price = exit_price
            open_trade.exit_reason = "eod"
            open_trade.pnl = total_pnl
            open_trade.return_pct = total_pnl / equity if equity else 0.0
            equity += remainder_pnl
            trades.append(open_trade)
            gate.register_closed_trade(last_ts, equity, total_pnl, len(annotated) - 1)
            equity_points[-1] = (last_ts, equity)

        equity_curve = pd.Series(
            data=[e for _, e in equity_points],
            index=pd.DatetimeIndex([t for t, _ in equity_points]),
            name="equity",
        )
        metrics = compute_metrics(trades, equity_curve)
        metrics["skipped_by_risk"] = float(skipped_by_risk)
        metrics["skipped_by_no_trade"] = float(skipped_by_no_trade)
        for reason, count in gate.state.skip_counts.items():
            metrics[f"skip_{reason}"] = float(count)
        return BacktestResult(
            trades=trades,
            equity_curve=equity_curve,
            metrics=metrics,
            annotated=annotated,
        )

    def _realize(self, trade: Trade, exit_price: float) -> float:
        return self._realize_size(trade, exit_price, trade.size)

    def _realize_size(self, trade: Trade, exit_price: float, size: float) -> float:
        direction = 1.0 if trade.side is Side.LONG else -1.0
        gross = direction * (exit_price - trade.entry_price) * size
        fee = _apply_fee(size * exit_price, self.backtest_config.fee_bps)
        return gross - fee
