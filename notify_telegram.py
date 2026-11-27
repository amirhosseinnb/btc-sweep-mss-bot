"""
Optional Telegram alerts for high-quality paper signals.

Requires env:
  TELEGRAM_BOT_TOKEN
  TELEGRAM_CHAT_ID

No-op when secrets are missing. Dedupes via data/telegram_notified.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib import parse, request

STATE_PATH = Path("data/telegram_notified.json")
MIN_SCORE_DEFAULT = 19


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {"notified": []}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"notified": []}


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _key(symbol: str, signal_time: str, side: str) -> str:
    return f"{symbol}|{signal_time}|{side}"


def send_telegram_message(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    body = parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = request.Request(url, data=body, method="POST")
    with request.urlopen(req, timeout=20) as resp:
        return 200 <= getattr(resp, "status", 200) < 300


def maybe_notify_paper_signal(
    *,
    symbol: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    score: Optional[float],
    score_quality: Optional[str],
    signal_time: str,
    min_score: int = MIN_SCORE_DEFAULT,
    preset: str = "javid",
) -> dict:
    """
    Notify when score >= min_score. Returns status dict for logs/CI.
    """
    status = {
        "attempted": False,
        "sent": False,
        "skipped_reason": None,
        "at_utc": datetime.now(timezone.utc).isoformat(),
    }
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        status["skipped_reason"] = "missing_telegram_secrets"
        return status

    if score is None or float(score) < min_score:
        status["skipped_reason"] = f"score_below_{min_score}"
        return status

    state = _load_state()
    notified = set(state.get("notified") or [])
    key = _key(symbol, signal_time, side)
    if key in notified:
        status["skipped_reason"] = "already_notified"
        return status

    side_fa = "خرید" if str(side).lower() == "long" else "فروش"
    text = (
        "AJV Paper Signal (read-only)\n"
        f"Preset: {preset}\n"
        f"{symbol} · {side_fa}\n"
        f"Score: {int(score)}/24 ({score_quality or '—'})\n"
        f"Entry: {entry}\n"
        f"SL: {stop_loss}\n"
        f"TP: {take_profit}\n"
        f"Time: {signal_time}\n"
        "سفارش واقعی ارسال نمی‌شود."
    )
    status["attempted"] = True
    try:
        ok = send_telegram_message(text)
        status["sent"] = bool(ok)
        if ok:
            notified.add(key)
            # Keep file bounded
            state["notified"] = list(notified)[-200:]
            state["last_sent_utc"] = status["at_utc"]
            _save_state(state)
        else:
            status["skipped_reason"] = "telegram_http_failed"
    except Exception as exc:  # noqa: BLE001
        status["skipped_reason"] = f"error:{exc}"
    return status


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Test Telegram notify wiring")
    p.add_argument("--test", action="store_true", help="Send a test ping if secrets exist")
    args = p.parse_args()
    if args.test:
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat:
            print("Telegram secrets missing — no-op")
            return
        ok = send_telegram_message("AJV test ping · read-only paper bot")
        print("sent" if ok else "failed")


if __name__ == "__main__":
    main()
