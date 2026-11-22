"""
Build docs/performance.json (+ share/) for the public UI market report.
Runs best + full-rulebook presets where data exists.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from backtester import Backtester
from jalali import dual_date
from paper_journal import READINESS_PATH, build_readiness, update_signal_outcomes
from rulebook import javid_backtest_config, javid_strategy_config
from run import load_ohlcv
from validate import best_backtest_config, best_strategy_config, walk_forward_folds


def _pf(v: float) -> float | None:
    if v == float("inf"):
        return None
    return float(v)


def _run(csv_path: Path, preset: str) -> dict:
    df = load_ohlcv(csv_path)
    if preset == "javid":
        cfg = javid_strategy_config()
        bt = javid_backtest_config()
    else:
        cfg = best_strategy_config()
        bt = best_backtest_config()
    m = Backtester(cfg, bt).run(df).metrics
    start = dual_date(df.index[0])
    end = dual_date(df.index[-1])
    return {
        "symbol": csv_path.stem.replace("usdt_4h", "").upper() + "USDT",
        "name": csv_path.stem.replace("usdt_4h", "").upper(),
        "name_fa": {"BTC": "بیت‌کوین", "ETH": "اتریوم", "SOL": "سولانا"}.get(
            csv_path.stem.replace("usdt_4h", "").upper(), csv_path.stem
        ),
        "preset": preset,
        "bars": len(df),
        "start": start,
        "end": end,
        "trades": int(m["n_trades"]),
        "win_rate": float(m["win_rate"]),
        "pnl": float(m["total_pnl"]),
        "max_drawdown": float(m["max_drawdown"]),
        "profit_factor": _pf(float(m["profit_factor"])),
        "final_equity": float(m["final_equity"]),
    }


def _wf_pack(csv_path: Path, *, preset: str) -> dict:
    df = load_ohlcv(csv_path)
    if preset == "javid":
        folds_df = walk_forward_folds(
            df,
            strategy=javid_strategy_config(),
            backtest=javid_backtest_config(),
        )
    else:
        folds_df = walk_forward_folds(df)

    rows: list[dict] = []
    for _, r in folds_df.iterrows():
        pf = r["profit_factor"]
        rows.append(
            {
                "start": dual_date(r["oos_start"]),
                "end": dual_date(r["oos_end"]),
                "bars": int(r["bars"]),
                "trades": int(r["trades"]),
                "win_rate": float(r["win_rate"]),
                "pnl": float(r["total_pnl"]),
                "max_drawdown": float(r["max_drawdown"]),
                "profit_factor": None if pf == float("inf") else float(pf),
                "final_equity": float(r["final_equity"]),
            }
        )
    pos = sum(1 for r in rows if r["pnl"] > 0)
    return {
        "preset": preset,
        "fold_days": 90,
        "positive_folds": pos,
        "total_folds": len(rows),
        "folds": rows,
    }


def build() -> dict:
    assets_best = []
    assets_javid = []
    for path in [
        Path("data/btcusdt_4h.csv"),
        Path("data/ethusdt_4h.csv"),
        Path("data/solusdt_4h.csv"),
    ]:
        if not path.exists():
            continue
        assets_best.append(_run(path, "best"))
        assets_javid.append(_run(path, "javid"))

    btc = Path("data/btcusdt_4h.csv")
    wf_best = _wf_pack(btc, preset="best") if btc.exists() else {
        "preset": "best", "fold_days": 90, "positive_folds": 0, "total_folds": 0, "folds": []
    }
    wf_javid = _wf_pack(btc, preset="javid") if btc.exists() else {
        "preset": "javid", "fold_days": 90, "positive_folds": 0, "total_folds": 0, "folds": []
    }

    # Prefer existing journal outcomes; if empty, still emit zeros.
    if Path("data/paper_signals.csv").exists():
        paper = update_signal_outcomes(days=400)
    elif Path("data/paper_outcomes.json").exists():
        paper = json.loads(Path("data/paper_outcomes.json").read_text(encoding="utf-8"))
    else:
        paper = {
            "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            "n_signals": 0,
            "n_closed": 0,
            "n_open": 0,
            "n_wins": 0,
            "win_rate": 0.0,
            "avg_pnl_r": 0.0,
        }

    readiness = build_readiness(
        paper_outcomes=paper,
        markets_javid=assets_javid,
        wf_javid=wf_javid,
    )

    now = datetime.now(timezone.utc)
    javid_cfg = javid_strategy_config()
    return {
        "generated_at": dual_date(now, with_time=True),
        "generated_note_fa": "گزارش بک‌تست آفلاین با کارمزد/اسلیپیج/ریسک؛ سفارش واقعی نیست.",
        "phase1_status": "complete_read_only",
        "assumptions_fa": [
            "سرمایه شروع: ۱۰٬۰۰۰ USDT",
            "ریسک هر معامله: ۱٪",
            f"حداقل R:R قوانین کامل = {javid_cfg.risk_reward:g}",
            "تایم‌فریم: ۴ ساعته",
            "ساعت پروژه: America/New_York",
            "سقف ۱ معامله/روز + کول‌داون ۲ بار بعد از ضرر (قوانین کامل)",
        ],
        "markets_best": assets_best,
        "markets_javid": assets_javid,
        "walk_forward_btc_best": wf_best,
        "walk_forward_btc_javid": wf_javid,
        "paper_outcomes": paper,
        "readiness": readiness,
        "rulebook_coverage": [
            {"id": "philosophy", "title_fa": "فلسفه قانون‌محور", "status": "done", "code": "philosophy.py"},
            {"id": "price_action", "title_fa": "Price Action (BOS/CHOCH)", "status": "done", "code": "price_action.py"},
            {"id": "ict", "title_fa": "ICT: FVG / OB / OTE / PD", "status": "done", "code": "ict.py"},
            {"id": "sweep_mss", "title_fa": "Liquidity Sweep + MSS", "status": "done", "code": "core_strategy.py"},
            {"id": "crt", "title_fa": "CRT Range / Sweep / Reclaim", "status": "done", "code": "crt.py"},
            {"id": "divergence", "title_fa": "Divergence Regular + Hidden", "status": "done", "code": "divergence.py"},
            {"id": "scoring", "title_fa": "امتیاز ۲۴تایی ۱۲×۰–۲", "status": "done", "code": "scoring.py"},
            {"id": "golden", "title_fa": "قانون طلایی Sweep+MSS+R:R≥۲", "status": "done", "code": "scoring.passes_critical_gates"},
            {"id": "targets", "title_fa": "هدف نقدینگی / CRT / Fixed RR", "status": "done", "code": "targets.py"},
            {"id": "risk", "title_fa": "ریسک ۱٪ + ضرر روزانه + ضرر متوالی", "status": "done", "code": "risk.py"},
            {"id": "no_trade", "title_fa": "No-Trade Gate", "status": "done", "code": "no_trade.py"},
            {"id": "manage", "title_fa": "Trade Management", "status": "done", "code": "trade_management.py"},
            {"id": "backtest", "title_fa": "Backtest + Walk-Forward", "status": "done", "code": "backtester.py / validate.py"},
            {"id": "paper", "title_fa": "Paper فقط‌خواندنی (قوانین کامل)", "status": "done", "code": "paper_trader.py"},
            {"id": "journal", "title_fa": "ژورنال Paper + آمادگی فاز ۲", "status": "done", "code": "paper_journal.py"},
            {"id": "report", "title_fa": "گزارش بازارها + شمسی در UI", "status": "done", "code": "performance.json"},
            {"id": "live_orders", "title_fa": "سفارش واقعی صرافی", "status": "phase2", "code": "عمداً خاموش تا پایداری"},
        ],
    }


def main() -> None:
    payload = build()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    for folder in (Path("docs"), Path("share")):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "performance.json").write_text(text, encoding="utf-8")
    if READINESS_PATH.exists():
        # Already written by build_readiness; also mirror under docs for Pages.
        readiness_text = READINESS_PATH.read_text(encoding="utf-8")
        for folder in (Path("docs"), Path("share")):
            (folder / "paper_readiness.json").write_text(readiness_text, encoding="utf-8")
    print(
        f"performance.json written | best_markets={len(payload['markets_best'])} "
        f"| javid={len(payload['markets_javid'])} "
        f"| wf_best={payload['walk_forward_btc_best']['total_folds']} "
        f"| wf_javid={payload['walk_forward_btc_javid']['total_folds']} "
        f"| phase2_ready={payload['readiness']['phase2_ready']}"
    )


if __name__ == "__main__":
    main()
