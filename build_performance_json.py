"""
Build docs/performance.json (+ share/) for the public UI market report.
Runs best + javid presets where data exists.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from backtester import BacktestConfig, Backtester
from jalali import dual_date
from rulebook import javid_strategy_config
from run import load_ohlcv
from trade_management import TradeManageConfig
from validate import best_strategy_config, walk_forward_folds


def _pf(v: float) -> float | None:
    if v == float("inf"):
        return None
    return float(v)


def _run(csv_path: Path, preset: str) -> dict:
    df = load_ohlcv(csv_path)
    if preset == "javid":
        cfg = javid_strategy_config()
        bt = BacktestConfig(
            initial_equity=10_000.0,
            risk_per_trade=0.01,
            fee_bps=4.0,
            slippage_bps=2.0,
            spread_bps=2.0,
            enable_risk_guards=True,
            trade_manage=TradeManageConfig(enable=True),
        )
    else:
        cfg = best_strategy_config()
        bt = BacktestConfig(
            initial_equity=10_000.0,
            risk_per_trade=0.01,
            fee_bps=4.0,
            slippage_bps=2.0,
            spread_bps=2.0,
            enable_risk_guards=True,
        )
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


def _wf(csv_path: Path) -> list[dict]:
    df = load_ohlcv(csv_path)
    folds = walk_forward_folds(df)
    rows: list[dict] = []
    for _, r in folds.iterrows():
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
    return rows


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
        if path.name.startswith("btc"):
            assets_javid.append(_run(path, "javid"))

    wf = _wf(Path("data/btcusdt_4h.csv")) if Path("data/btcusdt_4h.csv").exists() else []
    pos = sum(1 for r in wf if r["pnl"] > 0)

    return {
        "generated_note_fa": "گزارش بک‌تست آفلاین با کارمزد/اسلیپیج/ریسک؛ سفارش واقعی نیست.",
        "assumptions_fa": [
            "سرمایه شروع: ۱۰٬۰۰۰ USDT",
            "ریسک هر معامله: ۱٪",
            "حداقل R:R = ۲",
            "تایم‌فریم: ۴ ساعته",
            "ساعت پروژه: America/New_York",
        ],
        "markets_best": assets_best,
        "markets_javid": assets_javid,
        "walk_forward_btc_best": {
            "fold_days": 90,
            "positive_folds": pos,
            "total_folds": len(wf),
            "folds": wf,
        },
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
            {"id": "paper", "title_fa": "Paper فقط‌خواندنی (preset قوانین کامل)", "status": "done", "code": "paper_trader.py"},
            {"id": "live_orders", "title_fa": "سفارش واقعی صرافی", "status": "phase2", "code": "عمداً خاموش تا پایداری"},
        ],
    }


def main() -> None:
    payload = build()
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    for folder in (Path("docs"), Path("share")):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "performance.json").write_text(text, encoding="utf-8")
    print(
        f"performance.json written | best_markets={len(payload['markets_best'])} "
        f"| javid={len(payload['markets_javid'])} "
        f"| wf_folds={payload['walk_forward_btc_best']['total_folds']}"
    )


if __name__ == "__main__":
    main()
