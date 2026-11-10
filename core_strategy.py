"""
Rule-based SMC-style strategy primitives for Phase 1 MVP.

Detects swing points, liquidity sweeps, market structure shifts (MSS),
and emits long/short trade signals with fixed R:R risk parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

# Project clock: all session logic and display use New York local time.
DEFAULT_TIMEZONE = "America/New_York"
NY_TZ = ZoneInfo(DEFAULT_TIMEZONE)


class Side(str, Enum):
    LONG = "long"
    SHORT = "short"


# Session hour windows in America/New_York local time [start, end).
SESSION_WINDOWS: dict[str, tuple[tuple[float, float], ...]] = {
    "london": ((2.0, 12.0),),
    "newyork": ((8.0, 17.0),),
    "london_ny": ((2.0, 17.0),),  # London open through NY cash close
    "killzones": ((2.0, 5.0), (7.0, 10.0)),  # London / NY open killzones
}


@dataclass(frozen=True)
class SwingPoint:
    """A confirmed swing high or swing low."""

    index: int
    price: float
    kind: str  # "high" | "low"
    confirmed_at: int


@dataclass(frozen=True)
class SweepEvent:
    """Liquidity sweep of a prior swing level."""

    index: int
    side: Side  # LONG = bullish sweep, SHORT = bearish sweep
    swept_level: float
    sweep_extreme: float  # lowest wick (bull) or highest wick (bear)
    reference_swing_index: int
    opposite_swing_price: float  # MSS break level


@dataclass(frozen=True)
class Signal:
    """Executable trade signal produced on the MSS confirmation bar."""

    index: int
    side: Side
    entry: float
    stop_loss: float
    take_profit: float
    sweep_index: int
    risk_reward: float


@dataclass(frozen=True)
class StrategyConfig:
    swing_n: int = 3
    risk_reward: float = 2.0
    entry_mode: str = "mss_close"  # mss_close | first_retracement | fvg_retrace
    # Phase 1.5 quality filters (optional; default off keeps baseline MVP).
    require_displacement: bool = False
    atr_period: int = 14
    displacement_atr_mult: float = 1.5
    require_htf_bias: bool = False
    htf_rule: str = "1D"
    htf_ema_period: int = 20
    max_bars_sweep_to_mss: Optional[int] = None
    min_sweep_atr_mult: float = 0.0
    # Session filter (New York local hours). Off by default.
    require_session: bool = False
    session_mode: str = "london_ny"  # london | newyork | london_ny | killzones
    timezone: str = DEFAULT_TIMEZONE
    # CRT filters (prior NY-day range).
    require_crt_reclaim: bool = False
    require_crt_sweep: bool = False
    # Divergence + FVG (Phase 1.7).
    require_divergence: bool = False
    rsi_period: int = 14
    divergence_lookback: int = 40
    fvg_lookback_bars: int = 20
    max_bars_mss_to_fvg: int = 20

    def __post_init__(self) -> None:
        if self.swing_n < 1:
            raise ValueError("swing_n must be >= 1")
        if self.risk_reward < 2.0:
            raise ValueError("Phase-1 rule requires risk_reward >= 2.0")
        if self.entry_mode not in {"mss_close", "first_retracement", "fvg_retrace"}:
            raise ValueError(
                "entry_mode must be 'mss_close', 'first_retracement', or 'fvg_retrace'"
            )
        if self.atr_period < 1:
            raise ValueError("atr_period must be >= 1")
        if self.displacement_atr_mult <= 0:
            raise ValueError("displacement_atr_mult must be > 0")
        if self.htf_ema_period < 1:
            raise ValueError("htf_ema_period must be >= 1")
        if self.max_bars_sweep_to_mss is not None and self.max_bars_sweep_to_mss < 1:
            raise ValueError("max_bars_sweep_to_mss must be >= 1")
        if self.min_sweep_atr_mult < 0:
            raise ValueError("min_sweep_atr_mult must be >= 0")
        if self.session_mode not in SESSION_WINDOWS:
            raise ValueError(
                f"session_mode must be one of {sorted(SESSION_WINDOWS)}"
            )
        if self.rsi_period < 2:
            raise ValueError("rsi_period must be >= 2")
        if self.divergence_lookback < 5:
            raise ValueError("divergence_lookback must be >= 5")
        if self.fvg_lookback_bars < 1:
            raise ValueError("fvg_lookback_bars must be >= 1")
        if self.max_bars_mss_to_fvg < 1:
            raise ValueError("max_bars_mss_to_fvg must be >= 1")
        try:
            ZoneInfo(self.timezone)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid timezone: {self.timezone}") from exc


def to_project_timezone(
    index: pd.DatetimeIndex,
    timezone: str = DEFAULT_TIMEZONE,
) -> pd.DatetimeIndex:
    """Normalize timestamps to the project timezone (default: New York)."""
    tz = ZoneInfo(timezone)
    if index.tz is None:
        # Binance CSVs are UTC; assume naive stamps are UTC wall times.
        return index.tz_localize("UTC").tz_convert(tz)
    return index.tz_convert(tz)


def _require_ohlcv(
    df: pd.DataFrame,
    timezone: str = DEFAULT_TIMEZONE,
) -> pd.DataFrame:
    required = {"open", "high", "low", "close"}
    missing = required - {c.lower() for c in df.columns}
    if missing:
        raise ValueError(f"OHLCV frame missing columns: {sorted(missing)}")

    out = df.copy()
    out.columns = [c.lower() for c in out.columns]
    if not isinstance(out.index, pd.DatetimeIndex):
        if "timestamp" in out.columns:
            out["timestamp"] = pd.to_datetime(out["timestamp"], utc=True)
            out = out.set_index("timestamp")
        elif "date" in out.columns:
            out["date"] = pd.to_datetime(out["date"], utc=True)
            out = out.set_index("date")
    if isinstance(out.index, pd.DatetimeIndex):
        out.index = to_project_timezone(out.index, timezone=timezone)
    out = out.sort_index()
    return out


def detect_swing_points(df: pd.DataFrame, n: int = 3) -> list[SwingPoint]:
    """
    Detect swing highs/lows using an N-bar left and N-bar right window.

    A swing at bar i is only confirmed once bar i + N has printed.
    """
    if n < 1:
        raise ValueError("swing window n must be >= 1")

    data = _require_ohlcv(df)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    length = len(data)
    swings: list[SwingPoint] = []

    for i in range(n, length - n):
        left_h = highs[i - n : i]
        right_h = highs[i + 1 : i + n + 1]
        left_l = lows[i - n : i]
        right_l = lows[i + 1 : i + n + 1]

        if highs[i] > left_h.max() and highs[i] > right_h.max():
            swings.append(
                SwingPoint(
                    index=i,
                    price=float(highs[i]),
                    kind="high",
                    confirmed_at=i + n,
                )
            )
        if lows[i] < left_l.min() and lows[i] < right_l.min():
            swings.append(
                SwingPoint(
                    index=i,
                    price=float(lows[i]),
                    kind="low",
                    confirmed_at=i + n,
                )
            )

    swings.sort(key=lambda s: (s.confirmed_at, s.index))
    return swings


def detect_liquidity_sweeps(
    df: pd.DataFrame,
    swings: list[SwingPoint],
) -> list[SweepEvent]:
    """
    Bullish sweep: Low < recent Swing Low and Close > that Swing Low.
    Bearish sweep: High > recent Swing High and Close < that Swing High.
    """
    data = _require_ohlcv(df)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    closes = data["close"].to_numpy(dtype=float)
    sweeps: list[SweepEvent] = []

    # Incremental pointers — swings are sorted by confirmation time.
    confirmed: list[SwingPoint] = []
    cursor = 0

    for i in range(len(data)):
        while cursor < len(swings) and swings[cursor].confirmed_at <= i:
            confirmed.append(swings[cursor])
            cursor += 1

        swing_low = None
        swing_high = None
        for s in reversed(confirmed):
            if s.index >= i:
                continue
            if swing_low is None and s.kind == "low":
                swing_low = s
            elif swing_high is None and s.kind == "high":
                swing_high = s
            if swing_low is not None and swing_high is not None:
                break

        if swing_low is not None and lows[i] < swing_low.price and closes[i] > swing_low.price:
            if swing_high is not None:
                sweeps.append(
                    SweepEvent(
                        index=i,
                        side=Side.LONG,
                        swept_level=swing_low.price,
                        sweep_extreme=float(lows[i]),
                        reference_swing_index=swing_low.index,
                        opposite_swing_price=swing_high.price,
                    )
                )

        if swing_high is not None and highs[i] > swing_high.price and closes[i] < swing_high.price:
            if swing_low is not None:
                sweeps.append(
                    SweepEvent(
                        index=i,
                        side=Side.SHORT,
                        swept_level=swing_high.price,
                        sweep_extreme=float(highs[i]),
                        reference_swing_index=swing_high.index,
                        opposite_swing_price=swing_low.price,
                    )
                )

    return sweeps


def _infer_bar_hours(index: pd.DatetimeIndex) -> float:
    if len(index) < 2:
        return 1.0
    deltas = index.to_series().diff().dropna().dt.total_seconds() / 3600.0
    if deltas.empty:
        return 1.0
    return float(max(deltas.median(), 1.0 / 60.0))


def in_session_mask(
    index: pd.DatetimeIndex,
    session_mode: str = "london_ny",
    timezone: str = DEFAULT_TIMEZONE,
) -> np.ndarray:
    """
    True when a bar overlaps an allowed New York-local session window.

    Uses bar open time + inferred bar duration so 4H candles that merely
    overlap London/NY still qualify.
    """
    if session_mode not in SESSION_WINDOWS:
        raise ValueError(f"Unknown session_mode: {session_mode}")
    windows = SESSION_WINDOWS[session_mode]
    local_idx = to_project_timezone(index, timezone=timezone)
    bar_hours = _infer_bar_hours(local_idx)
    hours = local_idx.hour + local_idx.minute / 60.0

    mask = np.zeros(len(local_idx), dtype=bool)
    for start, end in windows:
        # Overlap test: [hour, hour+bar_hours) ∩ [start, end) nonempty
        mask |= (hours < end) & ((hours + bar_hours) > start)
    return mask


def _rr_targets(side: Side, entry: float, stop: float, rr: float) -> float:
    risk = abs(entry - stop)
    if risk <= 0:
        raise ValueError("invalid stop: zero or negative risk distance")
    if side == Side.LONG:
        return entry + rr * risk
    return entry - rr * risk


def compute_atr(df: pd.DataFrame, period: int = 14) -> np.ndarray:
    """Wilder-style ATR as a plain numpy array aligned to `df`."""
    data = _require_ohlcv(df)
    high = data["high"].to_numpy(dtype=float)
    low = data["low"].to_numpy(dtype=float)
    close = data["close"].to_numpy(dtype=float)
    prev_close = np.roll(close, 1)
    prev_close[0] = close[0]
    tr = np.maximum(high - low, np.maximum(np.abs(high - prev_close), np.abs(low - prev_close)))
    atr = np.full(len(data), np.nan, dtype=float)
    if len(data) < period:
        return atr
    atr[period - 1] = float(np.mean(tr[:period]))
    alpha = 1.0 / period
    for i in range(period, len(data)):
        atr[i] = atr[i - 1] * (1.0 - alpha) + tr[i] * alpha
    return atr


def compute_htf_bias_series(
    df: pd.DataFrame,
    rule: str = "1D",
    ema_period: int = 20,
    timezone: str = DEFAULT_TIMEZONE,
) -> pd.Series:
    """
    Higher-timeframe bias from completed HTF candles only (no look-ahead).

    Resamples on New York local calendar days by default.
    +1 = bullish (HTF close > HTF EMA), -1 = bearish, 0 = unknown/warmup.
    Mapped onto the LTF index via backward as-of join of the *previous*
    completed HTF bar.
    """
    data = _require_ohlcv(df, timezone=timezone)
    if not isinstance(data.index, pd.DatetimeIndex):
        raise ValueError("HTF bias requires a DatetimeIndex")

    # Resample on NY wall-clock days (tz-naive local times), then map back.
    flat = data.copy()
    flat.index = to_project_timezone(data.index, timezone=timezone).tz_localize(None)

    htf = (
        flat.resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last"})
        .dropna()
    )
    if htf.empty:
        return pd.Series(0, index=data.index, dtype=int)

    ema = htf["close"].ewm(span=ema_period, adjust=False).mean()
    raw_bias = np.where(htf["close"] > ema, 1, -1).astype(int)
    bias = pd.Series(raw_bias, index=htf.index, name="htf_bias")
    # Shift by 1 so bar T only sees HTF candle that closed before T.
    bias = bias.shift(1)

    mapped = bias.reindex(flat.index, method="ffill").fillna(0).astype(int)
    mapped.index = data.index
    return mapped


def _filter_sweeps_by_penetration(
    df: pd.DataFrame,
    sweeps: list[SweepEvent],
    atr: np.ndarray,
    min_mult: float,
) -> list[SweepEvent]:
    if min_mult <= 0:
        return sweeps
    highs = df["high"].to_numpy(dtype=float)
    lows = df["low"].to_numpy(dtype=float)
    kept: list[SweepEvent] = []
    for sw in sweeps:
        a = atr[sw.index]
        if not np.isfinite(a) or a <= 0:
            continue
        if sw.side == Side.LONG:
            penetration = sw.swept_level - lows[sw.index]
        else:
            penetration = highs[sw.index] - sw.swept_level
        if penetration >= min_mult * a:
            kept.append(sw)
    return kept


def generate_signals(
    df: pd.DataFrame,
    config: Optional[StrategyConfig] = None,
) -> tuple[pd.DataFrame, list[Signal]]:
    """
    Full pipeline: swings -> sweeps -> MSS -> entry signals.

    Bullish MSS: after a bullish sweep, a later bar closes above the most
    recent swing high referenced at sweep time.
    Bearish MSS: after a bearish sweep, a later bar closes below the most
    recent swing low referenced at sweep time.

    Optional Phase-1.5/1.7 filters:
      - Displacement on the MSS candle (body >= mult * ATR)
      - HTF bias alignment (completed higher-TF close vs EMA)
      - Session windows in America/New_York
      - CRT prior-day sweep / reclaim
      - Regular RSI divergence
      - FVG retracement entry after MSS
      - Max bars allowed between sweep and MSS
      - Minimum sweep wick penetration in ATR units
    """
    # Local imports avoid circular dependencies with helper modules.
    from crt import (
        compute_prior_day_crt_levels,
        is_reclaim_close,
        pierces_crt_boundary,
    )
    from divergence import divergence_seen_recently, regular_divergence_flags
    from ict import detect_fvgs, fvg_entry_price, fvg_touched, latest_fvg_between

    cfg = config or StrategyConfig()
    data = _require_ohlcv(df, timezone=cfg.timezone)
    swings = detect_swing_points(data, n=cfg.swing_n)
    sweeps = detect_liquidity_sweeps(data, swings)

    opens = data["open"].to_numpy(dtype=float)
    closes = data["close"].to_numpy(dtype=float)
    highs = data["high"].to_numpy(dtype=float)
    lows = data["low"].to_numpy(dtype=float)
    atr = compute_atr(data, period=cfg.atr_period)
    sweeps = _filter_sweeps_by_penetration(data, sweeps, atr, cfg.min_sweep_atr_mult)

    crt_high, crt_low = compute_prior_day_crt_levels(data, timezone=cfg.timezone)
    if cfg.require_crt_sweep:
        sweeps = [
            sw
            for sw in sweeps
            if pierces_crt_boundary(
                sw.side,
                high=float(highs[sw.index]),
                low=float(lows[sw.index]),
                crt_high=float(crt_high[sw.index]),
                crt_low=float(crt_low[sw.index]),
            )
        ]

    htf_bias = (
        compute_htf_bias_series(
            data,
            rule=cfg.htf_rule,
            ema_period=cfg.htf_ema_period,
            timezone=cfg.timezone,
        )
        if cfg.require_htf_bias
        else pd.Series(0, index=data.index, dtype=int)
    )
    htf_vals = htf_bias.to_numpy(dtype=int)

    annotated = data.copy()
    annotated["swing_high"] = np.nan
    annotated["swing_low"] = np.nan
    annotated["bullish_sweep"] = False
    annotated["bearish_sweep"] = False
    annotated["bullish_mss"] = False
    annotated["bearish_mss"] = False
    if not isinstance(data.index, pd.DatetimeIndex):
        session_ok = np.ones(len(data), dtype=bool)
    else:
        session_ok = (
            in_session_mask(data.index, cfg.session_mode, timezone=cfg.timezone)
            if cfg.require_session
            else np.ones(len(data), dtype=bool)
        )

    bull_div, bear_div = regular_divergence_flags(
        data,
        rsi_period=cfg.rsi_period,
        swing_n=cfg.swing_n,
        lookback=cfg.divergence_lookback,
    )
    fvgs = detect_fvgs(data)

    annotated["atr"] = atr
    annotated["htf_bias"] = htf_vals
    annotated["in_session"] = session_ok
    annotated["crt_high"] = crt_high
    annotated["crt_low"] = crt_low
    annotated["bull_div"] = bull_div
    annotated["bear_div"] = bear_div
    annotated["signal"] = pd.Series(pd.NA, index=annotated.index, dtype="string")

    swing_high_vals = annotated["swing_high"].to_numpy(copy=True)
    swing_low_vals = annotated["swing_low"].to_numpy(copy=True)
    for s in swings:
        if s.kind == "high":
            swing_high_vals[s.index] = s.price
        else:
            swing_low_vals[s.index] = s.price
    annotated["swing_high"] = swing_high_vals
    annotated["swing_low"] = swing_low_vals

    bullish_sweep_flags = np.zeros(len(annotated), dtype=bool)
    bearish_sweep_flags = np.zeros(len(annotated), dtype=bool)
    for sw in sweeps:
        if sw.side == Side.LONG:
            bullish_sweep_flags[sw.index] = True
        else:
            bearish_sweep_flags[sw.index] = True
    annotated["bullish_sweep"] = bullish_sweep_flags
    annotated["bearish_sweep"] = bearish_sweep_flags

    bullish_mss_flags = np.zeros(len(annotated), dtype=bool)
    bearish_mss_flags = np.zeros(len(annotated), dtype=bool)
    signal_vals = annotated["signal"].to_numpy(copy=True)

    sweeps_by_bar: dict[int, list[SweepEvent]] = {}
    for sw in sweeps:
        sweeps_by_bar.setdefault(sw.index, []).append(sw)

    signals: list[Signal] = []
    pending: Optional[SweepEvent] = None
    pending_reclaimed: bool = False
    # (sweep, mss_index, stop, optional_fvg)
    awaiting_retrace: Optional[tuple[SweepEvent, int, float, object | None]] = None

    def _passes_quality(side: Side, bar_i: int) -> bool:
        if cfg.require_session and not bool(session_ok[bar_i]):
            return False
        if cfg.require_displacement:
            a = atr[bar_i]
            if not np.isfinite(a) or a <= 0:
                return False
            body = abs(closes[bar_i] - opens[bar_i])
            if body < cfg.displacement_atr_mult * a:
                return False
        if cfg.require_htf_bias:
            b = int(htf_vals[bar_i])
            if side == Side.LONG and b <= 0:
                return False
            if side == Side.SHORT and b >= 0:
                return False
        if cfg.require_crt_reclaim and not pending_reclaimed:
            return False
        if cfg.require_divergence:
            flags = bull_div if side == Side.LONG else bear_div
            if not divergence_seen_recently(flags, bar_i, cfg.divergence_lookback):
                return False
        return True

    def _emit(sig: Signal) -> None:
        signals.append(sig)
        signal_vals[sig.index] = sig.side.value

    for i in range(len(data)):
        if pending is not None and cfg.max_bars_sweep_to_mss is not None:
            if i - pending.index > cfg.max_bars_sweep_to_mss:
                pending = None
                pending_reclaimed = False

        if awaiting_retrace is not None:
            _, mss_i, _, _ = awaiting_retrace
            if i - mss_i > cfg.max_bars_mss_to_fvg:
                awaiting_retrace = None

        # Refresh pending sweep — keep the latest unconfirmed sweep of either side.
        if i in sweeps_by_bar:
            pending = sweeps_by_bar[i][-1]
            awaiting_retrace = None
            # Sweep candle itself can already reclaim into the CRT range.
            pending_reclaimed = is_reclaim_close(
                pending.side,
                float(closes[i]),
                float(crt_high[i]),
                float(crt_low[i]),
            )

        if pending is not None and i > pending.index:
            if not pending_reclaimed and is_reclaim_close(
                pending.side,
                float(closes[i]),
                float(crt_high[i]),
                float(crt_low[i]),
            ):
                pending_reclaimed = True

            mss_hit = False
            if pending.side == Side.LONG and closes[i] > pending.opposite_swing_price:
                mss_hit = True
                bullish_mss_flags[i] = True
            elif pending.side == Side.SHORT and closes[i] < pending.opposite_swing_price:
                mss_hit = True
                bearish_mss_flags[i] = True

            if mss_hit:
                if not _passes_quality(pending.side, i):
                    # Keep pending if only reclaim is missing; otherwise drop.
                    if cfg.require_crt_reclaim and not pending_reclaimed:
                        continue
                    pending = None
                    pending_reclaimed = False
                    continue

                stop = float(pending.sweep_extreme)

                if cfg.entry_mode == "mss_close":
                    entry = float(closes[i])
                    try:
                        tp = _rr_targets(pending.side, entry, stop, cfg.risk_reward)
                    except ValueError:
                        pending = None
                        pending_reclaimed = False
                        continue
                    _emit(
                        Signal(
                            index=i,
                            side=pending.side,
                            entry=entry,
                            stop_loss=stop,
                            take_profit=tp,
                            sweep_index=pending.index,
                            risk_reward=cfg.risk_reward,
                        )
                    )
                    pending = None
                    pending_reclaimed = False
                elif cfg.entry_mode == "first_retracement":
                    awaiting_retrace = (pending, i, stop, None)
                    pending = None
                    pending_reclaimed = False
                elif cfg.entry_mode == "fvg_retrace":
                    # Prefer FVG formed between sweep and MSS; else any recent
                    # same-side FVG in the lookback window (relaxed Phase 1.8).
                    gap = latest_fvg_between(
                        fvgs,
                        side=pending.side,
                        start_index=pending.index,
                        end_index=i,
                    )
                    if gap is None:
                        start = max(0, i - cfg.fvg_lookback_bars)
                        gap = latest_fvg_between(
                            fvgs,
                            side=pending.side,
                            start_index=start,
                            end_index=i,
                        )
                    if gap is None:
                        # Still no FVG — skip this setup.
                        pending = None
                        pending_reclaimed = False
                        continue
                    awaiting_retrace = (pending, i, stop, gap)
                    pending = None
                    pending_reclaimed = False

        if awaiting_retrace is not None:
            sweep, mss_i, stop, gap = awaiting_retrace
            if i <= mss_i:
                continue

            filled = False
            entry = float(closes[i])
            if gap is not None:
                if fvg_touched(gap, float(highs[i]), float(lows[i])):
                    filled = True
                    entry = fvg_entry_price(gap, float(closes[i]))
            else:
                # Legacy midpoint retracement fallback.
                mid = (sweep.swept_level + stop) / 2.0
                if sweep.side == Side.LONG and lows[i] <= mid:
                    filled = True
                    entry = float(mid)
                elif sweep.side == Side.SHORT and highs[i] >= mid:
                    filled = True
                    entry = float(mid)

            if filled:
                # Invalid if entry is on the wrong side of stop.
                if sweep.side == Side.LONG and not (stop < entry):
                    awaiting_retrace = None
                    continue
                if sweep.side == Side.SHORT and not (stop > entry):
                    awaiting_retrace = None
                    continue
                try:
                    tp = _rr_targets(sweep.side, entry, stop, cfg.risk_reward)
                except ValueError:
                    awaiting_retrace = None
                    continue
                _emit(
                    Signal(
                        index=i,
                        side=sweep.side,
                        entry=entry,
                        stop_loss=stop,
                        take_profit=tp,
                        sweep_index=sweep.index,
                        risk_reward=cfg.risk_reward,
                    )
                )
                awaiting_retrace = None

    annotated["bullish_mss"] = bullish_mss_flags
    annotated["bearish_mss"] = bearish_mss_flags
    annotated["signal"] = pd.Series(signal_vals, index=annotated.index, dtype="string")
    return annotated, signals
