"""
Refresh read-only live market snapshot for the public report page.

Writes docs/live.json (+ share/live.json) used by the GitHub Pages UI.
Does NOT place any exchange orders.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from paper_trader import (
    already_logged,
    append_signal_log,
    fetch_closed_ohlcv,
    latest_mark_price,
)
from core_strategy import generate_signals
from validate import best_strategy_config


def build_snapshot(symbol: str = "BTCUSDT", timeframe: str = "4h", days: int = 400) -> dict:
    ohlcv = fetch_closed_ohlcv(symbol, timeframe, days)
    mark = latest_mark_price(symbol)
    annotated, signals = generate_signals(ohlcv, best_strategy_config())

    last_bar_time = ohlcv.index[-1]
    last_close = float(ohlcv["close"].iloc[-1])
    active = [s for s in signals if s.index == len(ohlcv) - 1]

    signal_payload = None
    if active:
        sig = active[0]
        signal_payload = {
            "side": sig.side.value,
            "entry": round(sig.entry, 2),
            "stop_loss": round(sig.stop_loss, 2),
            "take_profit": round(sig.take_profit, 2),
            "risk_reward": sig.risk_reward,
            "signal_time": last_bar_time.isoformat(),
        }
        log_path = Path("data/paper_signals.csv")
        if not already_logged(log_path, last_bar_time):
            append_signal_log(
                log_path,
                {
                    "signal_time": last_bar_time.isoformat(),
                    "checked_at_utc": datetime.now(timezone.utc).isoformat(),
                    "symbol": symbol,
                    "timeframe": timeframe,
                    "side": sig.side.value,
                    "entry": sig.entry,
                    "stop_loss": sig.stop_loss,
                    "take_profit": sig.take_profit,
                    "risk_reward": sig.risk_reward,
                    "mark_price": mark,
                    "status": "paper_signal_only",
                },
            )

    recent = [
        {
            "side": s.side.value,
            "entry": round(s.entry, 2),
            "stop_loss": round(s.stop_loss, 2),
            "take_profit": round(s.take_profit, 2),
            "bar_time": ohlcv.index[s.index].isoformat(),
        }
        for s in signals[-5:]
    ]

    return {
        "status": "online",
        "mode": "read_only_paper",
        "connected_to_market": True,
        "orders_enabled": False,
        "symbol": symbol,
        "timeframe": timeframe,
        "timezone": "America/New_York",
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "mark_price": round(mark, 2),
        "last_closed_bar": last_bar_time.isoformat(),
        "last_close": round(last_close, 2),
        "bars_used": len(ohlcv),
        "signals_total": len(signals),
        "active_signal": signal_payload,
        "recent_signals": recent,
        "note_fa": "اتصال فقط برای خواندن قیمت و سیگنال آزمایشی است؛ سفارش واقعی ارسال نمی‌شود.",
    }


def write_snapshot(snapshot: dict) -> None:
    payload = json.dumps(snapshot, ensure_ascii=False, indent=2)
    for folder in (Path("docs"), Path("share")):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "live.json").write_text(payload, encoding="utf-8")
        (folder / ".nojekyll").write_text("", encoding="utf-8")


def main() -> None:
    snapshot = build_snapshot()
    write_snapshot(snapshot)
    print(
        f"Live snapshot updated | {snapshot['symbol']} mark={snapshot['mark_price']} "
        f"| active={bool(snapshot['active_signal'])} | {snapshot['updated_at_utc']}"
    )


if __name__ == "__main__":
    main()
