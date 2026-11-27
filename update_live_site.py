"""
Refresh read-only live market snapshot for the public report page.

Writes docs/live.json (+ share/live.json) used by the GitHub Pages UI.
Uses the AJV Rulebook preset by default. Does NOT place any exchange orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from core_strategy import generate_signals
from jalali import dual_date
from live_diagnostics import (
    diagnose_no_trade,
    jalali_month_calendar,
    paper_journal_rows,
    paper_journal_summary,
)
from notify_telegram import maybe_notify_paper_signal
from paper_journal import OUTCOMES_PATH, READINESS_PATH
from paper_trader import (
    already_logged,
    append_signal_log,
    fetch_closed_ohlcv,
    latest_mark_price,
    signal_to_row,
    strategy_for_preset,
)
from scoring import ScoreQuality, parse_score_detail, quality_label_fa


QUALITY_FA = {
    ScoreQuality.NO_TRADE.value: quality_label_fa(ScoreQuality.NO_TRADE),
    ScoreQuality.WEAK.value: quality_label_fa(ScoreQuality.WEAK),
    ScoreQuality.REVIEW.value: quality_label_fa(ScoreQuality.REVIEW),
    ScoreQuality.GOOD.value: quality_label_fa(ScoreQuality.GOOD),
    ScoreQuality.A_PLUS.value: quality_label_fa(ScoreQuality.A_PLUS),
}


def _signal_public(sig, bar_time: str) -> dict:
    quality = sig.score_quality
    when = dual_date(bar_time, with_time=True)
    return {
        "side": sig.side.value,
        "entry": round(sig.entry, 2),
        "stop_loss": round(sig.stop_loss, 2),
        "take_profit": round(sig.take_profit, 2),
        "risk_reward": sig.risk_reward,
        "bar_time": bar_time,
        "bar_time_gregorian": when["gregorian"],
        "bar_time_jalali": when["jalali"],
        "bar_time_label": when["label"],
        "score": sig.score,
        "score_detail": sig.score_detail,
        "score_parts": parse_score_detail(sig.score_detail),
        "score_quality": quality,
        "score_quality_fa": QUALITY_FA.get(quality or "", None),
        "tp_reason": sig.tp_reason,
    }


def build_snapshot(
    symbol: str = "BTCUSDT",
    timeframe: str = "4h",
    days: int = 400,
    preset: str = "javid",
) -> dict:
    ohlcv = fetch_closed_ohlcv(symbol, timeframe, days)
    mark = latest_mark_price(symbol)
    cfg = strategy_for_preset(preset)
    annotated, signals = generate_signals(ohlcv, cfg)

    last_bar_time = ohlcv.index[-1]
    last_close = float(ohlcv["close"].iloc[-1])
    active = [s for s in signals if s.index == len(ohlcv) - 1]

    signal_payload = None
    notify_status = None
    if active:
        sig = active[0]
        signal_payload = _signal_public(sig, last_bar_time.isoformat())
        signal_payload["signal_time"] = last_bar_time.isoformat()
        log_path = Path("data/paper_signals.csv")
        if not already_logged(log_path, last_bar_time, symbol=symbol):
            append_signal_log(
                log_path,
                signal_to_row(
                    sig=sig,
                    last_bar_time=last_bar_time,
                    checked_at=datetime.now(timezone.utc).isoformat(),
                    symbol=symbol,
                    timeframe=timeframe,
                    mark=mark,
                    preset=preset,
                ),
            )
            notify_status = maybe_notify_paper_signal(
                symbol=symbol,
                side=sig.side.value,
                entry=float(sig.entry),
                stop_loss=float(sig.stop_loss),
                take_profit=float(sig.take_profit),
                score=sig.score,
                score_quality=sig.score_quality,
                signal_time=last_bar_time.isoformat(),
                preset=preset,
            )

    recent = [
        _signal_public(s, ohlcv.index[s.index].isoformat())
        for s in signals[-8:]
    ]
    recent.reverse()

    score_board = {
        "max": 24,
        "bands": [
            {"range": "0-11", "key": "no_trade", "label_fa": "بدون معامله"},
            {"range": "12-15", "key": "weak", "label_fa": "ضعیف"},
            {"range": "16-18", "key": "review", "label_fa": "متوسط / بررسی"},
            {"range": "19-21", "key": "good", "label_fa": "خوب"},
            {"range": "22-24", "key": "a_plus", "label_fa": "عالی A+"},
        ],
        "min_score": cfg.min_score,
        "reject_weak": cfg.reject_weak_scores,
    }

    no_trade = diagnose_no_trade(ohlcv, cfg)
    journal_rows = paper_journal_rows(limit=80)
    journal = {
        "summary": paper_journal_summary(journal_rows),
        "rows": journal_rows,
        "calendar": jalali_month_calendar(journal_rows),
    }
    # Prefer active signal breakdown; else newest recent with parts.
    score_breakdown = None
    if signal_payload and signal_payload.get("score_parts"):
        score_breakdown = {
            "source": "active",
            "score": signal_payload.get("score"),
            "quality": signal_payload.get("score_quality"),
            "parts": signal_payload.get("score_parts"),
        }
    elif recent:
        for item in recent:
            if item.get("score_parts"):
                score_breakdown = {
                    "source": "recent",
                    "score": item.get("score"),
                    "quality": item.get("score_quality"),
                    "bar_time_label": item.get("bar_time_label"),
                    "parts": item.get("score_parts"),
                }
                break

    updated = datetime.now(timezone.utc)
    last_dual = dual_date(last_bar_time, with_time=True)
    updated_dual = dual_date(updated, with_time=True)

    paper_outcomes = None
    readiness = None
    if OUTCOMES_PATH.exists():
        paper_outcomes = json.loads(OUTCOMES_PATH.read_text(encoding="utf-8"))
    if READINESS_PATH.exists():
        readiness = json.loads(READINESS_PATH.read_text(encoding="utf-8"))

    return {
        "status": "online",
        "mode": "read_only_paper",
        "connected_to_market": True,
        "orders_enabled": False,
        "preset": preset,
        "symbol": symbol,
        "timeframe": timeframe,
        "timezone": "America/New_York",
        "updated_at_utc": updated.isoformat(),
        "updated_at_gregorian": updated_dual["gregorian"],
        "updated_at_jalali": updated_dual["jalali"],
        "mark_price": round(mark, 2),
        "last_closed_bar": last_bar_time.isoformat(),
        "last_closed_bar_gregorian": last_dual["gregorian"],
        "last_closed_bar_jalali": last_dual["jalali"],
        "last_closed_bar_label": last_dual["label"],
        "last_close": round(last_close, 2),
        "bars_used": len(ohlcv),
        "signals_total": len(signals),
        "active_signal": signal_payload,
        "recent_signals": recent,
        "no_trade": no_trade,
        "score_board": score_board,
        "score_breakdown": score_breakdown,
        "risk_reward_min": cfg.risk_reward,
        "paper_outcomes": paper_outcomes,
        "paper_journal": journal,
        "readiness": readiness,
        "telegram_notify": notify_status,
        "note_fa": "اتصال فقط برای خواندن قیمت و سیگنال آزمایشی است؛ سفارش واقعی ارسال نمی‌شود. امتیازها طبق قوانین و منابع (۱۲×۰–۲).",
    }


def write_snapshot(snapshot: dict) -> None:
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    for folder in (Path("docs"), Path("share")):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "live.json").write_text(payload, encoding="utf-8")
        (folder / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    snapshot = build_snapshot(preset="javid")
    write_snapshot(snapshot)
    nt = snapshot.get("no_trade") or {}
    print(
        f"Live snapshot updated | preset={snapshot['preset']} | "
        f"{snapshot['symbol']} mark={snapshot['mark_price']} "
        f"| signals={snapshot['signals_total']} "
        f"| active={bool(snapshot['active_signal'])} "
        f"| no_trade={nt.get('status')} | {snapshot['updated_at_utc']}"
    )


if __name__ == "__main__":
    main()
