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
    return "∞" if v == float("inf") else f"{v:.2f}"


def _pnl_class(v: float) -> str:
    return "up" if v >= 0 else "down"


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
        "start": str(df.index[0])[:10],
        "end": str(df.index[-1])[:10],
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
            row["name"] = path.stem.replace("usdt_4h", "").upper()
            row["pair"] = path.stem.upper().replace("_", "/")
            assets.append(row)

    wf_path = Path("data/validation/wf_btcusdt_4h.csv")
    wf_rows = ""
    positive_folds = 0
    total_folds = 0
    if wf_path.exists():
        wf = pd.read_csv(wf_path)
        total_folds = len(wf)
        for _, r in wf.iterrows():
            pf = r["profit_factor"]
            pf_s = "∞" if pf == float("inf") else f"{pf:.2f}"
            pnl = float(r["total_pnl"])
            if pnl > 0:
                positive_folds += 1
            cls = _pnl_class(pnl)
            wf_rows += (
                f"<tr>"
                f"<td class='mono'>{str(r['oos_start'])[:10]} → {str(r['oos_end'])[:10]}</td>"
                f"<td>{int(r['trades'])}</td>"
                f"<td>{r['win_rate']*100:.1f}%</td>"
                f"<td class='{cls}'>{pnl:+.2f}</td>"
                f"<td class='mono'>{pf_s}</td>"
                f"</tr>"
            )

    btc = next((a for a in assets if a["name"] == "BTC"), None)
    asset_cards = ""
    for i, a in enumerate(assets):
        featured = " featured" if a["name"] == "BTC" else ""
        delay = 0.08 + i * 0.06
        asset_cards += f"""
        <article class="asset-card{featured}" style="animation-delay:{delay:.2f}s">
          <div class="asset-top">
            <div>
              <div class="asset-name">{a['name']}<span>/USDT</span></div>
              <div class="asset-range mono">{a['start']} → {a['end']}</div>
            </div>
            <div class="asset-badge">4H</div>
          </div>
          <div class="asset-pnl {_pnl_class(a['pnl'])}">{a['pnl']:+,.2f}</div>
          <div class="asset-grid">
            <div><span>Win</span><b>{a['win_rate']:.1f}%</b></div>
            <div><span>Trades</span><b>{a['trades']}</b></div>
            <div><span>PF</span><b>{_pf(a['pf'])}</b></div>
            <div><span>MaxDD</span><b>{a['mdd']:.2f}%</b></div>
          </div>
          <div class="asset-foot mono">Equity {a['equity']:,.2f} · {a['bars']:,} bars</div>
        </article>
        """

    headline_pnl = f"{btc['pnl']:+,.0f}" if btc else "—"
    headline_wr = f"{btc['win_rate']:.0f}%" if btc else "—"
    headline_pf = _pf(btc["pf"]) if btc else "—"

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TR Bot — Phase 1 Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Vazirmatn:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --bg0: #07110d;
      --bg1: #0c1a14;
      --panel: rgba(14, 28, 22, 0.72);
      --panel-solid: #102019;
      --text: #e9f6ef;
      --muted: #8eaa9a;
      --line: rgba(120, 180, 140, 0.18);
      --lime: #b6f26d;
      --mint: #5fe0a8;
      --amber: #f0c35a;
      --up: #7dffb3;
      --down: #ff8d7a;
      --shadow: 0 24px 60px rgba(0, 0, 0, 0.35);
      --radius: 22px;
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Vazirmatn", sans-serif;
      background:
        radial-gradient(900px 520px at 85% -10%, rgba(182, 242, 109, 0.16), transparent 55%),
        radial-gradient(700px 480px at 0% 20%, rgba(95, 224, 168, 0.10), transparent 50%),
        linear-gradient(180deg, var(--bg1), var(--bg0) 40%, #050c09);
      min-height: 100vh;
      line-height: 1.75;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.08;
      background-image:
        linear-gradient(rgba(182, 242, 109, 0.35) 1px, transparent 1px),
        linear-gradient(90deg, rgba(182, 242, 109, 0.35) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: radial-gradient(circle at 50% 20%, black, transparent 75%);
    }}
    .wrap {{
      position: relative;
      max-width: 1080px;
      margin: 0 auto;
      padding: 28px 18px 72px;
    }}
    .mono {{ font-family: "IBM Plex Mono", monospace; direction: ltr; unicode-bidi: plaintext; }}
    .brand-row {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 12px;
      margin-bottom: 22px;
      animation: rise 0.7s ease both;
    }}
    .logo {{
      display: flex;
      align-items: center;
      gap: 12px;
    }}
    .mark {{
      width: 42px;
      height: 42px;
      border-radius: 12px;
      background: linear-gradient(145deg, var(--lime), #5cb86a);
      box-shadow: 0 0 0 1px rgba(182, 242, 109, 0.35), 0 10px 30px rgba(182, 242, 109, 0.25);
      position: relative;
    }}
    .mark::after {{
      content: "";
      position: absolute;
      inset: 11px 9px 11px 9px;
      border-right: 3px solid #0a160f;
      border-bottom: 3px solid #0a160f;
      transform: skewX(-18deg);
    }}
    .logo strong {{
      display: block;
      font-size: 1.05rem;
      letter-spacing: 0.04em;
    }}
    .logo span {{ color: var(--muted); font-size: 0.82rem; }}
    .live-chip {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 8px 12px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(8, 20, 14, 0.7);
      color: var(--mint);
      font-size: 0.82rem;
    }}
    .live-chip i {{
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: var(--mint);
      box-shadow: 0 0 0 0 rgba(95, 224, 168, 0.7);
      animation: pulse 1.8s infinite;
    }}
    .hero {{
      position: relative;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 28px;
      padding: clamp(24px, 4vw, 40px);
      background:
        linear-gradient(135deg, rgba(16, 36, 28, 0.92), rgba(8, 18, 14, 0.88)),
        radial-gradient(600px 280px at 100% 0%, rgba(182, 242, 109, 0.18), transparent 60%);
      box-shadow: var(--shadow);
      animation: rise 0.8s ease both;
      animation-delay: 0.05s;
      margin-bottom: 22px;
    }}
    .hero::after {{
      content: "";
      position: absolute;
      width: 280px;
      height: 280px;
      right: -60px;
      bottom: -90px;
      border-radius: 50%;
      background: radial-gradient(circle, rgba(182, 242, 109, 0.22), transparent 70%);
      filter: blur(8px);
      animation: drift 8s ease-in-out infinite alternate;
    }}
    .kicker {{
      color: var(--lime);
      font-size: 0.9rem;
      font-weight: 600;
      margin-bottom: 10px;
      letter-spacing: 0.02em;
    }}
    h1 {{
      margin: 0;
      font-size: clamp(2rem, 5vw, 3.2rem);
      line-height: 1.15;
      font-weight: 800;
      letter-spacing: -0.02em;
      max-width: 14ch;
    }}
    .hero-copy {{
      margin: 14px 0 0;
      color: var(--muted);
      max-width: 38rem;
      font-size: 1.02rem;
    }}
    .hero-stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 28px;
      position: relative;
      z-index: 1;
    }}
    .stat {{
      padding: 16px;
      border-radius: 18px;
      background: rgba(4, 12, 9, 0.55);
      border: 1px solid var(--line);
      backdrop-filter: blur(8px);
    }}
    .stat span {{ display: block; color: var(--muted); font-size: 0.82rem; margin-bottom: 6px; }}
    .stat b {{
      font-family: "IBM Plex Mono", monospace;
      font-size: clamp(1.35rem, 3vw, 1.8rem);
      font-weight: 600;
      direction: ltr;
      unicode-bidi: plaintext;
    }}
    .section {{
      margin-top: 28px;
      animation: rise 0.8s ease both;
    }}
    .section h2 {{
      margin: 0 0 14px;
      font-size: 1.25rem;
      font-weight: 700;
    }}
    .section-note {{
      color: var(--muted);
      margin: -6px 0 16px;
      font-size: 0.92rem;
    }}
    .assets {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 14px;
    }}
    .asset-card {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 18px;
      backdrop-filter: blur(10px);
      animation: rise 0.8s ease both;
      transition: transform 0.25s ease, border-color 0.25s ease;
    }}
    .asset-card:hover {{
      transform: translateY(-3px);
      border-color: rgba(182, 242, 109, 0.35);
    }}
    .asset-card.featured {{
      background:
        linear-gradient(180deg, rgba(182, 242, 109, 0.10), transparent 40%),
        var(--panel-solid);
      border-color: rgba(182, 242, 109, 0.35);
    }}
    .asset-top {{ display: flex; justify-content: space-between; gap: 10px; }}
    .asset-name {{ font-size: 1.2rem; font-weight: 700; }}
    .asset-name span {{ color: var(--muted); font-weight: 500; font-size: 0.9rem; }}
    .asset-range {{ color: var(--muted); font-size: 0.78rem; margin-top: 2px; }}
    .asset-badge {{
      height: fit-content;
      padding: 4px 10px;
      border-radius: 999px;
      background: rgba(182, 242, 109, 0.12);
      color: var(--lime);
      font-size: 0.78rem;
      font-weight: 600;
    }}
    .asset-pnl {{
      margin: 16px 0 12px;
      font-family: "IBM Plex Mono", monospace;
      font-size: 1.7rem;
      font-weight: 600;
      direction: ltr;
      unicode-bidi: plaintext;
    }}
    .up {{ color: var(--up); }}
    .down {{ color: var(--down); }}
    .asset-grid {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 8px;
    }}
    .asset-grid div {{
      background: rgba(0, 0, 0, 0.22);
      border-radius: 12px;
      padding: 10px 8px;
      text-align: center;
    }}
    .asset-grid span {{ display: block; color: var(--muted); font-size: 0.72rem; }}
    .asset-grid b {{ font-size: 0.95rem; }}
    .asset-foot {{
      margin-top: 12px;
      color: var(--muted);
      font-size: 0.78rem;
    }}
    .panel {{
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: var(--radius);
      padding: 18px;
      backdrop-filter: blur(10px);
      overflow: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 560px;
    }}
    th, td {{
      padding: 12px 10px;
      border-bottom: 1px solid var(--line);
      text-align: right;
      font-size: 0.92rem;
    }}
    th {{
      color: var(--muted);
      font-weight: 600;
      font-size: 0.8rem;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .two-col {{
      display: grid;
      grid-template-columns: 1.2fr 0.8fr;
      gap: 14px;
    }}
    .list {{
      margin: 0;
      padding: 0;
      list-style: none;
      display: grid;
      gap: 10px;
    }}
    .list li {{
      display: flex;
      gap: 10px;
      align-items: flex-start;
      color: var(--muted);
      background: rgba(0, 0, 0, 0.18);
      border-radius: 14px;
      padding: 12px 14px;
    }}
    .list li::before {{
      content: "";
      width: 8px;
      height: 8px;
      margin-top: 8px;
      border-radius: 50%;
      background: var(--lime);
      flex: 0 0 auto;
      box-shadow: 0 0 12px rgba(182, 242, 109, 0.6);
    }}
    .commands {{
      display: grid;
      gap: 10px;
    }}
    .cmd {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
      background: #07140f;
      border: 1px solid var(--line);
      border-radius: 14px;
      padding: 12px 14px;
    }}
    .cmd code {{
      color: var(--lime);
      font-family: "IBM Plex Mono", monospace;
      font-size: 0.82rem;
      direction: ltr;
      unicode-bidi: plaintext;
      white-space: nowrap;
      overflow: auto;
    }}
    .cmd small {{ color: var(--muted); font-size: 0.78rem; white-space: nowrap; }}
    .footer {{
      margin-top: 28px;
      color: var(--muted);
      font-size: 0.85rem;
      text-align: center;
    }}
    @keyframes rise {{
      from {{ opacity: 0; transform: translateY(14px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes pulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(95, 224, 168, 0.55); }}
      70% {{ box-shadow: 0 0 0 10px rgba(95, 224, 168, 0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(95, 224, 168, 0); }}
    }}
    @keyframes drift {{
      from {{ transform: translateY(0); }}
      to {{ transform: translateY(-18px); }}
    }}
    @media (max-width: 800px) {{
      .hero-stats, .two-col {{ grid-template-columns: 1fr; }}
      .asset-grid {{ grid-template-columns: repeat(2, 1fr); }}
      h1 {{ max-width: none; }}
      .cmd {{ flex-direction: column; align-items: flex-start; }}
    }}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="brand-row">
      <div class="logo">
        <div class="mark" aria-hidden="true"></div>
        <div>
          <strong>TR BOT</strong>
          <span>btc-sweep-mss · Phase 1</span>
        </div>
      </div>
      <div class="live-chip"><i></i> Report Ready</div>
    </div>

    <header class="hero">
      <div class="kicker">قانون‌محور · Sweep → MSS → Risk Guards</div>
      <h1>TR BOT</h1>
      <p class="hero-copy">
        بک‌تست آفلاین استراتژی ICT-lite روی کریپتو، با تمرکز روی BTC 4H،
        فیلتر سشن نیویورک، هزینه واقعی و گارد ریسک.
      </p>
      <div class="hero-stats">
        <div class="stat"><span>BTC PnL</span><b class="{_pnl_class(btc['pnl']) if btc else ''}">{headline_pnl}</b></div>
        <div class="stat"><span>Win Rate</span><b>{headline_wr}</b></div>
        <div class="stat"><span>Profit Factor</span><b>{headline_pf}</b></div>
      </div>
    </header>

    <section class="section" style="animation-delay:0.12s">
      <h2>نتایج Full-sample</h2>
      <p class="section-note">Preset = best · Fee 4bps · Slip 2bps · Spread 2bps · Risk guards ON</p>
      <div class="assets">
        {asset_cards}
      </div>
    </section>

    <section class="section two-col" style="animation-delay:0.18s">
      <div>
        <h2>Walk-Forward BTC 4H</h2>
        <p class="section-note">پنجره‌های OOS نودروزه · {positive_folds}/{total_folds} فولد مثبت</p>
        <div class="panel">
          <table>
            <thead>
              <tr><th>بازه</th><th>Trades</th><th>Win%</th><th>PnL</th><th>PF</th></tr>
            </thead>
            <tbody>
              {wf_rows if wf_rows else "<tr><td colspan='5'>فایل walk-forward پیدا نشد</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
      <div>
        <h2>منطق فعلی</h2>
        <p class="section-note">هستهٔ فاز ۱ بدون سفارش واقعی</p>
        <ul class="list">
          <li>Swing High/Low با N=3</li>
          <li>Liquidity Sweep + MSS</li>
          <li>HTF Bias روزانه + سشن London/NY</li>
          <li>SL روی ویک سویپ · TP با R:R ≥ 1:2</li>
          <li>ضرر روزانه ۳٪ و قفل ۳ ضرر متوالی</li>
          <li>Paper Trader فقط‌خواندنی برای BTC 4H</li>
        </ul>
      </div>
    </section>

    <section class="section" style="animation-delay:0.24s">
      <h2>اجرای محلی</h2>
      <div class="commands">
        <div class="cmd"><code>python run.py --csv data/btcusdt_4h.csv --preset best</code><small>بک‌تست</small></div>
        <div class="cmd"><code>python validate.py</code><small>Walk-Forward</small></div>
        <div class="cmd"><code>python paper_trader.py --once</code><small>سیگنال کاغذی</small></div>
      </div>
    </section>

    <div class="footer">
      این صفحه فقط گزارش Phase 1 است · بدون اتصال زنده به صرافی
    </div>
  </div>
</body>
</html>
"""
    out_share = Path("share") / "index.html"
    out_docs = Path("docs") / "index.html"
    out_share.parent.mkdir(parents=True, exist_ok=True)
    out_docs.parent.mkdir(parents=True, exist_ok=True)
    out_share.write_text(html, encoding="utf-8")
    out_docs.write_text(html, encoding="utf-8")
    # Keep Pages happy with plain HTML.
    (Path("docs") / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote shareable report -> {out_share.resolve()}")
    print(f"Wrote GitHub Pages report -> {out_docs.resolve()}")


if __name__ == "__main__":
    main()
