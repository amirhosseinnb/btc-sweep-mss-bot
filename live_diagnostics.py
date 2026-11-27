"""
Live diagnostics for the public UI: No-Trade reasons + paper journal rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from core_strategy import StrategyConfig, generate_signals
from jalali import dual_date
from paper_journal import SIGNALS_PATH, load_signal_log
from scoring import ScoreQuality, quality_label_fa


def diagnose_no_trade(
    ohlcv: pd.DataFrame,
    cfg: StrategyConfig,
    *,
    lookback: int = 16,
) -> dict:
    """Explain why the latest closed bar has no Rulebook signal."""
    annotated, signals = generate_signals(ohlcv, cfg)
    i = len(annotated) - 1
    last_ts = annotated.index[i]
    active = [s for s in signals if s.index == i]
    if active:
        sig = active[0]
        return {
            "status": "signal",
            "status_fa": "سیگنال فعال",
            "bar_time": dual_date(last_ts, with_time=True),
            "reasons_fa": [],
            "checks": [],
            "side": sig.side.value,
            "score": sig.score,
            "score_quality": sig.score_quality,
        }

    start = max(0, i - lookback + 1)
    window = annotated.iloc[start : i + 1]
    in_session = bool(annotated["in_london_ny"].iloc[i]) if "in_london_ny" in annotated else True
    htf = int(annotated["htf_bias"].iloc[i]) if "htf_bias" in annotated else 0
    recent_bull_sw = bool(window["bullish_sweep"].any()) if "bullish_sweep" in window else False
    recent_bear_sw = bool(window["bearish_sweep"].any()) if "bearish_sweep" in window else False
    recent_bull_mss = bool(window["bullish_mss"].any()) if "bullish_mss" in window else False
    recent_bear_mss = bool(window["bearish_mss"].any()) if "bearish_mss" in window else False
    recent_div = False
    for col in ("bull_div", "bear_div", "bull_hid_div", "bear_hid_div"):
        if col in window.columns and bool(window[col].any()):
            recent_div = True
            break

    checks = [
        {"id": "session", "ok": (not cfg.require_session) or in_session, "label_fa": "داخل سشن London/NY"},
        {"id": "htf", "ok": (not cfg.require_htf_bias) or htf != 0, "label_fa": "جهت HTF مشخص"},
        {"id": "sweep", "ok": recent_bull_sw or recent_bear_sw, "label_fa": f"Sweep در {lookback} کندل اخیر"},
        {"id": "mss", "ok": recent_bull_mss or recent_bear_mss, "label_fa": f"MSS/BOS در {lookback} کندل اخیر"},
        {"id": "divergence", "ok": (not cfg.require_divergence) or recent_div, "label_fa": "Divergence در پنجرهٔ اخیر"},
    ]

    reasons: list[str] = []
    for c in checks:
        if not c["ok"]:
            reasons.append(c["label_fa"] + " برقرار نیست")

    # Compare with a looser baseline: if baseline fires on last bar, javid filters blocked it.
    baseline = StrategyConfig(
        require_htf_bias=True,
        require_session=True,
        session_mode="london_ny",
        entry_mode="mss_close",
    )
    _, base_sigs = generate_signals(ohlcv, baseline)
    base_active = [s for s in base_sigs if s.index == i]
    if base_active and not active:
        reasons.append(
            "ستاپ خام روی preset پایه دیده شد، ولی فیلترهای قوانین کامل (CRT/امتیاز/Divergence) آن را رد کردند"
        )

    if not reasons:
        reasons.append(
            "الان ستاپ کامل نیست — یا Sweep→MSS کامل نشده یا امتیاز/confluence به حد قوانین کامل نرسیده"
        )

    return {
        "status": "no_trade",
        "status_fa": "بدون معامله",
        "bar_time": dual_date(last_ts, with_time=True),
        "reasons_fa": reasons,
        "checks": checks,
        "lookback_bars": lookback,
        "htf_bias": htf,
        "in_session": in_session,
    }


def paper_journal_rows(
    path: Path = SIGNALS_PATH,
    *,
    limit: int = 40,
) -> list[dict]:
    """Public journal rows newest-first for the site table."""
    df = load_signal_log(path)
    if df.empty:
        return []

    rows: list[dict] = []
    # Sort by signal_time descending
    df = df.copy()
    df["_ts"] = pd.to_datetime(df["signal_time"], utc=True, errors="coerce")
    df = df.sort_values("_ts", ascending=False)

    for _, r in df.head(limit).iterrows():
        ts = r["_ts"]
        when = dual_date(ts, with_time=True) if pd.notna(ts) else {
            "gregorian": str(r.get("signal_time") or ""),
            "jalali": "",
            "label": str(r.get("signal_time") or ""),
        }
        exit_when = None
        if pd.notna(r.get("exit_time")):
            exit_when = dual_date(pd.to_datetime(r["exit_time"], utc=True), with_time=True)

        quality = r.get("score_quality")
        quality_s = str(quality) if pd.notna(quality) else None
        outcome = str(r.get("outcome_status") or "pending")
        win = r.get("win")
        win_b = None if pd.isna(win) else bool(win)
        pnl_r = r.get("pnl_r")
        pnl_r_f = None if pd.isna(pnl_r) else float(pnl_r)

        result_fa = "باز"
        if outcome == "closed":
            if win_b is True:
                result_fa = "برد"
            elif win_b is False:
                result_fa = "باخت"
            else:
                result_fa = "بسته"
        elif outcome == "pending":
            result_fa = "در انتظار"

        source = str(r.get("source") or "unknown")
        source_fa = {
            "live_paper": "زنده",
            "historical_seed": "بک‌فیل",
        }.get(source, source)

        rows.append(
            {
                "signal_time": when,
                "symbol": str(r.get("symbol") or ""),
                "side": str(r.get("side") or ""),
                "side_fa": "خرید" if str(r.get("side")).lower() == "long" else "فروش",
                "entry": _num(r.get("entry")),
                "stop_loss": _num(r.get("stop_loss")),
                "take_profit": _num(r.get("take_profit")),
                "score": _int(r.get("score")),
                "score_quality": quality_s,
                "score_quality_fa": (
                    quality_label_fa(ScoreQuality(quality_s))
                    if quality_s in {q.value for q in ScoreQuality}
                    else None
                ),
                "score_detail": None if pd.isna(r.get("score_detail")) else str(r.get("score_detail")),
                "outcome_status": outcome,
                "result_fa": result_fa,
                "exit_reason": None if pd.isna(r.get("exit_reason")) else str(r.get("exit_reason")),
                "exit_time": exit_when,
                "pnl_r": pnl_r_f,
                "win": win_b,
                "source": source,
                "source_fa": source_fa,
                "preset": str(r.get("preset") or "javid"),
            }
        )
    return rows


def paper_journal_summary(rows: list[dict]) -> dict:
    closed = [r for r in rows if r.get("outcome_status") == "closed"]
    wins = [r for r in closed if r.get("win") is True]
    live = [r for r in rows if r.get("source") == "live_paper"]
    seed = [r for r in rows if r.get("source") == "historical_seed"]
    return {
        "n_rows": len(rows),
        "n_closed": len(closed),
        "n_wins": len(wins),
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "n_live": len(live),
        "n_seed": len(seed),
        "avg_pnl_r": (
            sum(float(r["pnl_r"]) for r in closed if r.get("pnl_r") is not None) / len(closed)
            if closed
            else 0.0
        ),
    }


def downsample_equity(equity: pd.Series, *, max_points: int = 96) -> list[dict]:
    """Compact equity + drawdown series for the UI SVG chart."""
    if equity is None or equity.empty:
        return []
    eq = equity.dropna()
    if eq.empty:
        return []
    n = len(eq)
    if n <= max_points:
        idxs = list(range(n))
    else:
        step = max(1, n // max_points)
        idxs = list(range(0, n, step))
        if idxs[-1] != n - 1:
            idxs.append(n - 1)

    peak = float("-inf")
    out: list[dict] = []
    for i in idxs:
        ts = eq.index[i]
        val = float(eq.iloc[i])
        peak = max(peak, val)
        dd = 0.0 if peak <= 0 else (peak - val) / peak
        out.append(
            {
                "t": dual_date(ts),
                "equity": round(val, 2),
                "drawdown": round(dd, 5),
            }
        )
    return out


def market_warning(row: dict) -> Optional[str]:
    """Persian caution badge for weak markets on the full-rulebook preset."""
    name = row.get("name")
    pf = row.get("profit_factor")
    pnl = float(row.get("pnl") or 0.0)
    if name == "ETH" and (pnl < 0 or (pf is not None and float(pf) < 1.0)):
        return "هشدار: روی قوانین کامل فعلاً ضعیف/منفی است — فقط پایش مقایسه‌ای، نه سیگنال اصلی"
    if pf is not None and float(pf) < 1.0 and pnl < 0:
        return "نتیجهٔ بک‌تست این نماد زیر خط سود است"
    return None


def _num(v) -> Optional[float]:
    if v is None or (isinstance(v, float) and pd.isna(v)) or pd.isna(v):
        return None
    try:
        return round(float(v), 2)
    except (TypeError, ValueError):
        return None


def _int(v) -> Optional[int]:
    if v is None or pd.isna(v):
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None
