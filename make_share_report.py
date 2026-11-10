"""
Build a single self-contained HTML report friends can open without installing Python.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backtester import BacktestConfig, Backtester
from core_strategy import StrategyConfig
from run import load_ohlcv


def _pf(v: float) -> str:
    return "∞" if v == float("inf") else f"{v:.3f}"


def run_best(csv_path: Path) -> dict:
    df = load_ohlcv(csv_path)
    cfg = StrategyConfig(
        require_htf_bias=True,
        require_session=True,
        session_mode="london_ny",
    )
    bt = BacktestConfig(
        initial_equity=10_000.0,
        risk_per_trade=0.01,
        fee_bps=4.0,
        slippage_bps=2.0,
        spread_bps=2.0,
        enable_risk_guards=True,
    )
    m = Backtester(cfg, bt).run(df).metrics
    return {
        "bars": len(df),
        "start": str(df.index[0]),
        "end": str(df.index[-1]),
        "trades": int(m["n_trades"]),
        "win_rate": m["win_rate"] * 100.0,
        "pnl": m["total_pnl"],
        "mdd": m["max_drawdown"] * 100.0,
        "pf": m["profit_factor"],
        "equity": m["final_equity"],
    }


def main() -> None:
    assets = []
    for path in [
        Path("data/btcusdt_4h.csv"),
        Path("data/ethusdt_4h.csv"),
        Path("data/solusdt_4h.csv"),
    ]:
        if path.exists():
            row = run_best(path)
            row["name"] = path.stem.upper()
            assets.append(row)

    wf_path = Path("data/validation/wf_btcusdt_4h.csv")
    wf_rows = ""
    if wf_path.exists():
        wf = pd.read_csv(wf_path)
        for _, r in wf.iterrows():
            pf = r["profit_factor"]
            pf_s = "∞" if pf == float("inf") else f"{pf:.2f}"
            wf_rows += (
                f"<tr><td>{str(r['oos_start'])[:10]} → {str(r['oos_end'])[:10]}</td>"
                f"<td>{int(r['trades'])}</td>"
                f"<td>{r['win_rate']*100:.1f}%</td>"
                f"<td>{r['total_pnl']:.2f}</td>"
                f"<td>{pf_s}</td></tr>"
            )

    asset_rows = "".join(
        f"<tr><td>{a['name']}</td><td>{a['bars']}</td><td>{a['trades']}</td>"
        f"<td>{a['win_rate']:.1f}%</td><td>{a['pnl']:.2f}</td>"
        f"<td>{a['mdd']:.2f}%</td><td>{_pf(a['pf'])}</td>"
        f"<td>{a['equity']:.2f}</td></tr>"
        for a in assets
    )

    btc = next((a for a in assets if a["name"].startswith("BTC")), None)
    headline = (
        f"BTC 4H · PnL {btc['pnl']:.0f} · Win {btc['win_rate']:.0f}% · PF {_pf(btc['pf'])}"
        if btc
        else "Rule-based Sweep / MSS Bot"
    )

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TR Bot — Phase 1 Report</title>
  <style>
    :root {{
      --bg: #0f1419;
      --card: #1a222c;
      --text: #e7eef7;
      --muted: #93a4b8;
      --accent: #3dd6c6;
      --line: #2a3644;
      --good: #3dd68c;
      --bad: #ff6b6b;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Tahoma, sans-serif;
      background:
        radial-gradient(1200px 600px at 10% -10%, #1d3a3a 0%, transparent 50%),
        radial-gradient(900px 500px at 100% 0%, #24304a 0%, transparent 45%),
        var(--bg);
      color: var(--text);
      line-height: 1.7;
    }}
    .wrap {{ max-width: 980px; margin: 0 auto; padding: 32px 20px 64px; }}
    h1 {{ font-size: clamp(1.6rem, 3vw, 2.2rem); margin: 0 0 8px; }}
    .sub {{ color: var(--muted); margin-bottom: 28px; }}
    .hero {{
      background: linear-gradient(135deg, #1c2b33, #17202a);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 24px;
      margin-bottom: 22px;
    }}
    .pill {{
      display: inline-block;
      background: rgba(61, 214, 198, 0.12);
      color: var(--accent);
      border: 1px solid rgba(61, 214, 198, 0.35);
      border-radius: 999px;
      padding: 4px 12px;
      font-size: 0.85rem;
      margin-bottom: 12px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .metric {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 14px;
    }}
    .metric b {{ display: block; font-size: 1.25rem; }}
    .metric span {{ color: var(--muted); font-size: 0.85rem; }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 18px;
      margin-top: 16px;
    }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.95rem; }}
    th, td {{ padding: 10px 8px; border-bottom: 1px solid var(--line); text-align: right; }}
    th {{ color: var(--muted); font-weight: 600; }}
    ul {{ margin: 8px 0 0; padding-right: 18px; color: var(--muted); }}
    code {{
      background: #0c1117;
      padding: 2px 6px;
      border-radius: 6px;
      direction: ltr;
      display: inline-block;
    }}
    .footer {{ margin-top: 28px; color: var(--muted); font-size: 0.85rem; }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="hero">
      <div class="pill">Phase 1 · Offline Backtest + Paper Signals</div>
      <h1>ربات قانون‌محور ICT / Sweep / MSS</h1>
      <div class="sub">{headline}</div>
      <div class="grid">
        <div class="metric"><span>Preset</span><b>best</b></div>
        <div class="metric"><span>تایم‌زون</span><b>New York</b></div>
        <div class="metric"><span>ریسک/ترید</span><b>1%</b></div>
        <div class="metric"><span>هزینه</span><b>fee+slip+spread</b></div>
      </div>
    </div>

    <div class="card">
      <h2>نتایج Full-sample</h2>
      <table>
        <thead>
          <tr>
            <th>نماد</th><th>Bars</th><th>Trades</th><th>Win%</th>
            <th>PnL</th><th>MaxDD</th><th>PF</th><th>Equity</th>
          </tr>
        </thead>
        <tbody>
          {asset_rows}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>Walk-Forward BTC 4H (پنجره‌های ۹۰ روزه)</h2>
      <table>
        <thead>
          <tr><th>بازه OOS</th><th>Trades</th><th>Win%</th><th>PnL</th><th>PF</th></tr>
        </thead>
        <tbody>
          {wf_rows if wf_rows else "<tr><td colspan='5'>فایل walk-forward پیدا نشد</td></tr>"}
        </tbody>
      </table>
    </div>

    <div class="card">
      <h2>منطق فعلی</h2>
      <ul>
        <li>Swing High/Low با پنجره N=3</li>
        <li>Liquidity Sweep + Market Structure Shift</li>
        <li>فیلتر HTF Bias (روزانه) + سشن London/NY</li>
        <li>SL روی ویک سویپ · TP با R:R حداقل ۱:۲</li>
        <li>گارد ریسک: ضرر روزانه ۳٪ و ۳ ضرر متوالی</li>
        <li>Paper Trader فقط‌خواندنی برای BTC 4H (بدون سفارش واقعی)</li>
      </ul>
    </div>

    <div class="card">
      <h2>اجرای محلی</h2>
      <ul>
        <li><code>python run.py --csv data/btcusdt_4h.csv --preset best</code></li>
        <li><code>python validate.py</code></li>
        <li><code>python paper_trader.py --once</code></li>
      </ul>
    </div>

    <div class="footer">
      ساخته‌شده برای اشتراک نتایج Phase 1 · این صفحه فقط گزارش است و اتصال زنده به صرافی ندارد.
    </div>
  </div>
</body>
</html>
"""
    out = Path("share") / "index.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"Wrote shareable report -> {out.resolve()}")


if __name__ == "__main__":
    main()
