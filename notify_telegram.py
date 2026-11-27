"""
Optional Telegram alerts for high-quality paper signals (group-friendly).

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
SITE_URL = "https://amirhosseinnb.github.io/btc-sweep-mss-bot/"


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


def _api(token: str, method: str, params: Optional[dict] = None) -> dict:
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        body = parse.urlencode(params).encode("utf-8")
        req = request.Request(url, data=body, method="POST")
    else:
        req = request.Request(url, method="GET")
    with request.urlopen(req, timeout=20) as resp:
        raw = resp.read().decode("utf-8")
    return json.loads(raw)


def send_telegram_message(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat_id:
        return False
    data = _api(
        token,
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": "true",
        },
    )
    return bool(data.get("ok"))


def _chats_from_updates(updates: list[dict]) -> list[dict]:
    found: dict[str, dict] = {}
    for upd in updates:
        msg = (
            upd.get("message")
            or upd.get("edited_message")
            or upd.get("my_chat_member")
            or upd.get("channel_post")
            or {}
        )
        chat = msg.get("chat") or {}
        if not chat and isinstance(upd.get("my_chat_member"), dict):
            chat = (upd.get("my_chat_member") or {}).get("chat") or {}
        if not chat.get("id"):
            continue
        cid = str(chat["id"])
        found[cid] = {
            "id": cid,
            "type": chat.get("type"),
            "title": chat.get("title") or chat.get("username") or chat.get("first_name") or "",
        }
    return list(found.values())


def diagnose_bot(token: str) -> dict:
    """One getUpdates call only — Telegram deletes updates after they are fetched."""
    me = _api(token, "getMe")
    hook = _api(token, "getWebhookInfo")
    updates_payload = _api(token, "getUpdates", {"limit": "100", "timeout": "0"})
    updates = updates_payload.get("result") or []
    return {
        "me": me.get("result") or {},
        "webhook": hook.get("result") or {},
        "update_count": len(updates),
        "updates_ok": bool(updates_payload.get("ok")),
        "chats": _chats_from_updates(updates),
    }


def format_group_signal(
    *,
    symbol: str,
    side: str,
    entry: float,
    stop_loss: float,
    take_profit: float,
    score: float,
    score_quality: Optional[str],
    signal_time: str,
    preset: str,
) -> str:
    side_fa = "خرید (Long)" if str(side).lower() == "long" else "فروش (Short)"
    q = score_quality or "—"
    return (
        "📡 AJV · سیگنال Paper (فقط‌خواندنی)\n"
        "────────────────\n"
        f"نماد: {symbol}\n"
        f"سمت: {side_fa}\n"
        f"امتیاز: {int(score)}/24 · {q}\n"
        f"ورود: {entry}\n"
        f"حد ضرر: {stop_loss}\n"
        f"حد سود: {take_profit}\n"
        f"Preset: {preset}\n"
        f"زمان: {signal_time}\n"
        "────────────────\n"
        "⚠️ سفارش واقعی ارسال نمی‌شود.\n"
        f"گزارش: {SITE_URL}"
    )


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
    """Notify when score >= min_score. Returns status dict for logs/CI."""
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

    text = format_group_signal(
        symbol=symbol,
        side=side,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        score=float(score),
        score_quality=score_quality,
        signal_time=signal_time,
        preset=preset,
    )
    status["attempted"] = True
    try:
        ok = send_telegram_message(text)
        status["sent"] = bool(ok)
        if ok:
            notified.add(key)
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

    p = argparse.ArgumentParser(description="AJV Telegram notify / discover helpers")
    p.add_argument("--test", action="store_true", help="Send a test ping to TELEGRAM_CHAT_ID")
    p.add_argument(
        "--discover",
        action="store_true",
        help="List recent chat ids seen by the bot (needs TELEGRAM_BOT_TOKEN)",
    )
    p.add_argument(
        "--clear-webhook",
        action="store_true",
        help="Delete webhook so getUpdates/discover works",
    )
    args = p.parse_args()

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if args.clear_webhook:
        if not token:
            print("Set TELEGRAM_BOT_TOKEN first.")
            raise SystemExit(1)
        data = _api(token, "deleteWebhook", {"drop_pending_updates": "false"})
        print("webhook cleared" if data.get("ok") else data)
        return

    if args.discover:
        if not token:
            print("Set TELEGRAM_BOT_TOKEN first.")
            raise SystemExit(1)
        diag = diagnose_bot(token)
        me = diag["me"]
        print(
            f"Bot: @{me.get('username')} | privacy_read_all={me.get('can_read_all_group_messages')}"
        )
        wh = diag["webhook"].get("url") or ""
        if wh:
            print(f"WARNING: webhook is set ({wh}) — getUpdates may stay empty.")
            print("Clear it with: python notify_telegram.py --clear-webhook")
        print(f"Pending updates: {diag['update_count']}")
        chats = diag.get("chats") or []
        if not chats:
            print(
                "\nNo chats yet. Do ALL of these, then retry:\n"
                "  1) BotFather → /setprivacy → Disable\n"
                "  2) Add @bot to the GROUP\n"
                "  3) In the GROUP send: @your_bot_username hi\n"
                "  4) Also open PRIVATE chat with the bot and send /start\n"
                "Alternative: add @RawDataBot or @getidsbot to the group and read chat id."
            )
            raise SystemExit(2)
        print("Chats the bot can see:")
        for c in chats:
            mark = " ← GROUP/SUPERGROUP" if str(c["id"]).startswith("-") else ""
            print(f"  id={c['id']}  type={c['type']}  title={c['title']}{mark}")
        return

    if args.test:
        if not token or not chat:
            print("Need TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
            raise SystemExit(1)
        ok = send_telegram_message(
            "✅ AJV وصل شد به گروه\n"
            "از این به بعد سیگنال Paper با امتیاز ≥۱۹ اینجا می‌آید.\n"
            "سفارش واقعی ارسال نمی‌شود.\n"
            f"{SITE_URL}"
        )
        print("sent" if ok else "failed")
        raise SystemExit(0 if ok else 1)

    p.print_help()


if __name__ == "__main__":
    main()
