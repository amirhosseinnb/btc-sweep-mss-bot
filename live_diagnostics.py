"""
Live diagnostics for the public UI: No-Trade reasons + paper journal rows.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from core_strategy import StrategyConfig, generate_signals
from jalali import dual_date, gregorian_to_jalali
from paper_journal import SIGNALS_PATH, load_signal_log
from scoring import ScoreQuality, parse_score_detail, quality_label_fa


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

        detail = None if pd.isna(r.get("score_detail")) else str(r.get("score_detail"))
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
                "score_detail": detail,
                "score_parts": parse_score_detail(detail),
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


def _bucket_stats(rows: list[dict]) -> dict:
    closed = [r for r in rows if r.get("outcome_status") == "closed"]
    wins = [r for r in closed if r.get("win") is True]
    return {
        "n_rows": len(rows),
        "n_closed": len(closed),
        "n_wins": len(wins),
        "win_rate": (len(wins) / len(closed)) if closed else 0.0,
        "avg_pnl_r": (
            sum(float(r["pnl_r"]) for r in closed if r.get("pnl_r") is not None) / len(closed)
            if closed
            else 0.0
        ),
    }


def paper_journal_summary(rows: list[dict]) -> dict:
    live = [r for r in rows if r.get("source") == "live_paper"]
    seed = [r for r in rows if r.get("source") == "historical_seed"]
    overall = _bucket_stats(rows)
    return {
        **overall,
        "n_live": len(live),
        "n_seed": len(seed),
        "live": _bucket_stats(live),
        "seed": _bucket_stats(seed),
        "note_fa": "آمار live از مانیتور واقعی جدا از بک‌فیل تاریخی است.",
    }


def jalali_month_calendar(rows: list[dict], *, now: Optional[pd.Timestamp] = None) -> dict:
    """Build a Jalali month heatmap of paper signals (wins/losses/open)."""
    ts = now or pd.Timestamp.now(tz="UTC")
    if isinstance(ts, pd.Timestamp):
        gy, gm, gd = int(ts.year), int(ts.month), int(ts.day)
    else:
        gy, gm, gd = ts.year, ts.month, ts.day
    jy, jm, _jd = gregorian_to_jalali(gy, gm, gd)

    # If current Jalali month is empty, fall back to newest signal's month.
    def _parse_j(label: str) -> Optional[tuple[int, int, int]]:
        parts = str(label).split(" ")[0].split("/")
        if len(parts) < 3:
            return None
        try:
            return int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            return None

    has_current = False
    for r in rows:
        parsed = _parse_j((r.get("signal_time") or {}).get("jalali") or "")
        if parsed and parsed[0] == jy and parsed[1] == jm:
            has_current = True
            break
    if not has_current and rows:
        for r in rows:
            parsed = _parse_j((r.get("signal_time") or {}).get("jalali") or "")
            if parsed:
                jy, jm = parsed[0], parsed[1]
                break

    # Days in Jalali month
    if jm <= 6:
        days_in_month = 31
    elif jm <= 11:
        days_in_month = 30
    else:
        # Esfand: 29 or 30 — use 30 and allow empty trailing
        days_in_month = 30

    month_names = {
        1: "فروردین", 2: "اردیبهشت", 3: "خرداد", 4: "تیر",
        5: "مرداد", 6: "شهریور", 7: "مهر", 8: "آبان",
        9: "آذر", 10: "دی", 11: "بهمن", 12: "اسفند",
    }

    by_day: dict[int, dict] = {
        d: {"day": d, "n": 0, "wins": 0, "losses": 0, "open": 0, "signals": []}
        for d in range(1, days_in_month + 1)
    }

    for r in rows:
        label = (r.get("signal_time") or {}).get("jalali") or ""
        # expected: YYYY/MM/DD ...
        parts = str(label).split(" ")[0].split("/")
        if len(parts) < 3:
            continue
        try:
            ry, rm, rd = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if ry != jy or rm != jm:
            continue
        if rd not in by_day:
            continue
        cell = by_day[rd]
        cell["n"] += 1
        if r.get("win") is True:
            cell["wins"] += 1
        elif r.get("win") is False:
            cell["losses"] += 1
        else:
            cell["open"] += 1
        cell["signals"].append(
            {
                "symbol": r.get("symbol"),
                "side_fa": r.get("side_fa"),
                "score": r.get("score"),
                "result_fa": r.get("result_fa"),
            }
        )

    return {
        "jy": jy,
        "jm": jm,
        "title_fa": f"{month_names.get(jm, str(jm))} {jy}",
        "days_in_month": days_in_month,
        "days": [by_day[d] for d in range(1, days_in_month + 1)],
        "totals": {
            "n": sum(c["n"] for c in by_day.values()),
            "wins": sum(c["wins"] for c in by_day.values()),
            "losses": sum(c["losses"] for c in by_day.values()),
        },
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
