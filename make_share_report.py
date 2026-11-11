"""
Build a professional product demo page for Phase 1 (GitHub Pages + share/).
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
    eth = next((a for a in assets if a["name"] == "ETH"), None)
    sol = next((a for a in assets if a["name"] == "SOL"), None)
    name_fa = {"BTC": "بیت‌کوین", "ETH": "اتریوم", "SOL": "سولانا"}
    asset_rows = ""
    asset_cards = ""
    for a in assets:
        featured = " featured" if a["name"] == "BTC" else ""
        fa = name_fa.get(a["name"], a["name"])
        asset_rows += f"""
        <tr class="{featured.strip()}">
          <td><strong>{fa}</strong><span class="muted"> ({a['name']})</span></td>
          <td class="mono {_pnl_class(a['pnl'])}">{a['pnl']:+,.2f}</td>
          <td class="mono">{a['win_rate']:.1f}%</td>
          <td class="mono">{a['trades']}</td>
          <td class="mono">{_pf(a['pf'])}</td>
          <td class="mono">{a['mdd']:.2f}%</td>
          <td class="mono">{a['equity']:,.0f}</td>
        </tr>
        """
        note = "تمرکز اصلی فاز ۱" if a["name"] == "BTC" else "بررسی مقایسه‌ای روی ارز مهم دیگر"
        asset_cards += f"""
        <article class="result-card{featured}">
          <div class="result-top">
            <strong>{fa}</strong>
            <span>{note}</span>
          </div>
          <div class="result-pnl {_pnl_class(a['pnl'])}">{a['pnl']:+,.0f} USDT</div>
          <div class="result-grid">
            <div><span>درصد برد</span><b>{a['win_rate']:.0f}%</b></div>
            <div><span>تعداد معامله</span><b>{a['trades']}</b></div>
            <div><span>قدرت سود</span><b>{_pf(a['pf'])}</b></div>
            <div><span>بیشترین افت</span><b>{a['mdd']:.1f}%</b></div>
          </div>
        </article>
        """

    headline_pnl = f"{btc['pnl']:+,.0f}" if btc else "—"
    headline_wr = f"{btc['win_rate']:.0f}%" if btc else "—"
    headline_pf = _pf(btc["pf"]) if btc else "—"
    btc_equity = f"{btc['equity']:,.0f}" if btc else "—"
    btc_range = f"{btc['start']} → {btc['end']}" if btc else "—"
    eth_pnl = f"{eth['pnl']:+,.0f}" if eth else "—"
    sol_pnl = f"{sol['pnl']:+,.0f}" if sol else "—"

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="description" content="AJV (Amir · Javid · Vahid) — سیستم معاملاتی قانون‌محور برای کریپتو با بک‌تست، مدیریت ریسک و مانیتور زنده فقط‌خواندنی." />
  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate" />
  <title>AJV — Amir · Javid · Vahid</title>
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Sora:wght@500;600;700&family=Vazirmatn:wght@400;500;600;700;800&display=swap" rel="stylesheet" />
  <style>
    :root {{
      --ink: #07090d;
      --ink-2: #0d121a;
      --panel: rgba(16, 22, 32, 0.78);
      --line: rgba(160, 190, 220, 0.12);
      --text: #eef3f8;
      --muted: #8b9bb0;
      --accent: #3fd0c9;
      --accent-2: #f0b429;
      --up: #3dd68c;
      --down: #ff6b6b;
      --shadow: 0 30px 80px rgba(0, 0, 0, 0.45);
    }}
    * {{ box-sizing: border-box; }}
    html {{ scroll-behavior: smooth; }}
    body {{
      margin: 0;
      color: var(--text);
      font-family: "Vazirmatn", sans-serif;
      background: var(--ink);
      line-height: 1.75;
      overflow-x: hidden;
    }}
    .mono {{ font-family: "IBM Plex Mono", monospace; direction: ltr; unicode-bidi: plaintext; }}
    .muted {{ color: var(--muted); }}
    .brand-en {{ font-family: "Sora", sans-serif; letter-spacing: 0.04em; }}

    /* —— Hero: one composition —— */
    .hero {{
      position: relative;
      min-height: 100vh;
      min-height: 100dvh;
      display: grid;
      align-items: end;
      padding: 28px 22px 40px;
      isolation: isolate;
    }}
    .hero-bg {{
      position: absolute; inset: 0; z-index: -2;
      background:
        linear-gradient(180deg, rgba(7,9,13,0.15) 0%, rgba(7,9,13,0.55) 45%, rgba(7,9,13,0.96) 100%),
        radial-gradient(900px 500px at 70% 20%, rgba(63,208,201,0.18), transparent 55%),
        radial-gradient(700px 420px at 10% 80%, rgba(240,180,41,0.08), transparent 50%),
        linear-gradient(135deg, #0a1018, #07090d);
    }}
    .hero-chart {{
      position: absolute; inset: 0; z-index: -1; opacity: 0.55;
      background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 1200 700' preserveAspectRatio='none'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='0' y2='1'%3E%3Cstop stop-color='%233fd0c9' stop-opacity='0.35'/%3E%3Cstop offset='1' stop-color='%233fd0c9' stop-opacity='0'/%3E%3C/linearGradient%3E%3C/defs%3E%3Cpath d='M0 520 L80 500 L160 530 L240 410 L320 430 L400 300 L480 340 L560 220 L640 260 L720 180 L800 210 L880 140 L960 190 L1040 120 L1120 160 L1200 90 L1200 700 L0 700 Z' fill='url(%23g)'/%3E%3Cpath d='M0 520 L80 500 L160 530 L240 410 L320 430 L400 300 L480 340 L560 220 L640 260 L720 180 L800 210 L880 140 L960 190 L1040 120 L1120 160 L1200 90' fill='none' stroke='%233fd0c9' stroke-width='2.5' stroke-linecap='round'/%3E%3C/svg%3E");
      background-size: cover;
      background-position: center 30%;
      animation: chartRise 1.4s ease both;
    }}
    .hero-grid {{
      position: absolute; inset: 0; z-index: -1; opacity: 0.12;
      background-image:
        linear-gradient(rgba(63,208,201,0.5) 1px, transparent 1px),
        linear-gradient(90deg, rgba(63,208,201,0.5) 1px, transparent 1px);
      background-size: 64px 64px;
      mask-image: linear-gradient(180deg, black, transparent 80%);
    }}
    .topbar {{
      position: absolute; top: 0; right: 0; left: 0;
      display: flex; justify-content: space-between; align-items: center;
      padding: 22px clamp(18px, 4vw, 40px);
      animation: fadeUp 0.7s ease both;
    }}
    .logo {{
      display: flex; align-items: center; gap: 12px;
    }}
    .mark {{
      width: 40px; height: 40px; border-radius: 10px;
      background: linear-gradient(145deg, var(--accent), #1a8f8a);
      display: grid; place-items: center;
      font-family: "Sora", sans-serif; font-weight: 700; font-size: 0.72rem;
      color: #041214; letter-spacing: 0.04em;
    }}
    .logo-text strong {{
      display: block;
      font-family: "Sora", sans-serif; font-size: 1.2rem; font-weight: 700;
      letter-spacing: 0.12em;
    }}
    .logo-text span {{
      display: block; color: var(--muted); font-size: 0.78rem; margin-top: 2px;
    }}
    .status-pill {{
      display: inline-flex; align-items: center; gap: 8px;
      padding: 7px 12px; border: 1px solid var(--line);
      background: rgba(7,9,13,0.55); backdrop-filter: blur(8px);
      font-size: 0.78rem; color: var(--accent);
    }}
    .status-pill i {{
      width: 7px; height: 7px; border-radius: 50%; background: var(--accent);
      animation: pulse 1.8s infinite;
    }}
    .hero-content {{
      max-width: 1100px; margin: 0 auto; width: 100%;
      padding-bottom: 8vh;
      animation: fadeUp 0.9s ease both 0.1s;
    }}
    .hero-brand {{
      font-family: "Sora", sans-serif;
      font-size: clamp(3.2rem, 11vw, 7.5rem);
      font-weight: 700; line-height: 0.92;
      letter-spacing: -0.04em; margin: 0 0 18px;
    }}
    .hero-brand span {{
      display: block; font-size: 0.22em; letter-spacing: 0.22em;
      color: var(--accent); font-weight: 600; margin-bottom: 12px;
    }}
    .hero-line {{
      margin: 0; max-width: 34rem; color: var(--muted); font-size: 1.08rem;
    }}
    .cta-row {{
      display: flex; flex-wrap: wrap; gap: 12px; margin-top: 28px;
    }}
    .btn {{
      display: inline-flex; align-items: center; justify-content: center;
      padding: 12px 20px; text-decoration: none; font-weight: 600; font-size: 0.92rem;
      border: 1px solid transparent; transition: transform 0.2s ease, background 0.2s ease, border-color 0.2s ease;
    }}
    .btn:hover {{ transform: translateY(-2px); }}
    .btn-primary {{
      background: var(--accent); color: #041214;
    }}
    .btn-ghost {{
      background: transparent; color: var(--text); border-color: var(--line);
    }}
    .btn-ghost:hover {{ border-color: rgba(63,208,201,0.45); }}

    .wrap {{
      max-width: 1100px; margin: 0 auto; padding: 0 22px 90px;
    }}

    /* —— Live terminal —— */
    .terminal {{
      margin-top: -28px;
      border: 1px solid var(--line);
      background:
        linear-gradient(180deg, rgba(18,26,38,0.95), rgba(10,14,22,0.98));
      box-shadow: var(--shadow);
      overflow: hidden;
      animation: fadeUp 0.8s ease both;
    }}
    .term-bar {{
      display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;
      padding: 14px 18px; border-bottom: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
    }}
    .term-bar h2 {{
      margin: 0; font-size: 0.95rem; font-weight: 700;
      font-family: "Sora", sans-serif; letter-spacing: 0.04em;
    }}
    .term-meta {{ font-size: 0.78rem; color: var(--muted); }}
    .term-grid {{
      display: grid; grid-template-columns: 1.4fr 1fr; gap: 0;
    }}
    .term-metrics {{
      display: grid; grid-template-columns: repeat(2, 1fr); gap: 1px;
      background: var(--line);
      border-left: 1px solid var(--line);
    }}
    .metric {{
      background: rgba(7,9,13,0.55); padding: 18px 16px;
    }}
    .metric span {{
      display: block; color: var(--muted); font-size: 0.75rem;
      margin-bottom: 6px; letter-spacing: 0.02em;
    }}
    .metric b {{
      font-family: "IBM Plex Mono", monospace; font-size: 1.25rem;
      direction: ltr; unicode-bidi: plaintext; font-weight: 600;
    }}
    .signal-pane {{
      padding: 22px 20px; display: flex; flex-direction: column; justify-content: center;
      min-height: 180px;
    }}
    .signal-pane .label {{
      font-size: 0.75rem; color: var(--muted); margin-bottom: 8px;
      font-family: "Sora", sans-serif; letter-spacing: 0.12em; text-transform: uppercase;
    }}
    .signal-pane .state {{
      font-size: 1.35rem; font-weight: 700; margin-bottom: 8px;
    }}
    .signal-pane .state.wait {{ color: var(--muted); }}
    .signal-pane .state.hot {{ color: var(--accent-2); }}
    .signal-pane .detail {{
      color: var(--muted); font-size: 0.9rem;
      font-family: "IBM Plex Mono", monospace; direction: ltr; unicode-bidi: plaintext;
    }}
    .term-foot {{
      padding: 12px 18px; border-top: 1px solid var(--line);
      font-size: 0.8rem; color: var(--muted);
      display: flex; justify-content: space-between; gap: 10px; flex-wrap: wrap;
    }}
    .badge {{
      display: inline-block; padding: 2px 8px; border: 1px solid var(--line);
      font-size: 0.72rem; color: var(--accent);
    }}
    .refresh-strip {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: center;
      padding: 14px 18px; border-top: 1px solid var(--line);
      background: rgba(255,255,255,0.02);
    }}
    .refresh-item span {{
      display: block; color: var(--muted); font-size: 0.75rem; margin-bottom: 4px;
    }}
    .refresh-item b {{
      font-family: "IBM Plex Mono", monospace; font-size: 1rem;
      direction: ltr; unicode-bidi: plaintext; font-weight: 600;
    }}
    .refresh-btn {{
      appearance: none; border: 1px solid rgba(63,208,201,0.45);
      background: rgba(63,208,201,0.12); color: var(--accent);
      padding: 12px 16px; font-family: "Vazirmatn", sans-serif; font-weight: 700;
      font-size: 0.9rem; cursor: pointer; transition: background 0.2s ease, transform 0.2s ease;
      white-space: nowrap;
    }}
    .refresh-btn:hover:not(:disabled) {{
      background: rgba(63,208,201,0.22); transform: translateY(-1px);
    }}
    .refresh-btn:disabled {{
      opacity: 0.6; cursor: wait;
    }}
    .refresh-note {{
      grid-column: 1 / -1; color: var(--muted); font-size: 0.78rem; margin: 0;
    }}

    section {{ margin-top: 72px; }}
    .sec-kicker {{
      font-family: "Sora", sans-serif; font-size: 0.75rem; letter-spacing: 0.18em;
      color: var(--accent); margin-bottom: 10px; font-weight: 600;
    }}
    h3.sec-title {{
      margin: 0 0 10px; font-size: clamp(1.6rem, 3vw, 2.1rem); font-weight: 800;
      letter-spacing: -0.02em; max-width: 18ch;
    }}
    .sec-lead {{
      margin: 0 0 28px; color: var(--muted); max-width: 40rem; font-size: 1.02rem;
    }}

    .pillars {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 1px;
      background: var(--line); border: 1px solid var(--line);
    }}
    .pillar {{
      background: var(--ink-2); padding: 24px 20px;
    }}
    .pillar strong {{
      display: block; font-size: 1.05rem; margin-bottom: 8px;
    }}
    .pillar p {{ margin: 0; color: var(--muted); font-size: 0.92rem; }}

    .pipeline {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px;
    }}
    .pipe {{
      border-top: 2px solid var(--accent); padding-top: 16px;
    }}
    .pipe .n {{
      font-family: "Sora", sans-serif; font-size: 0.75rem; color: var(--accent);
      letter-spacing: 0.12em; margin-bottom: 8px;
    }}
    .pipe h4 {{ margin: 0 0 8px; font-size: 1.02rem; }}
    .pipe p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}

    .kpi-strip {{
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 1px;
      background: var(--line); border: 1px solid var(--line); margin-bottom: 22px;
    }}
    .kpi {{
      background: var(--ink-2); padding: 20px 16px;
    }}
    .kpi span {{ display: block; color: var(--muted); font-size: 0.78rem; margin-bottom: 6px; }}
    .kpi b {{
      font-family: "IBM Plex Mono", monospace; font-size: 1.4rem;
      direction: ltr; unicode-bidi: plaintext;
    }}

    .table-shell {{
      border: 1px solid var(--line); overflow: auto;
      background: rgba(13,18,26,0.8);
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 720px; }}
    th, td {{
      padding: 14px 12px; border-bottom: 1px solid var(--line);
      text-align: right; font-size: 0.9rem;
    }}
    th {{
      color: var(--muted); font-weight: 600; font-size: 0.75rem;
      letter-spacing: 0.04em; background: rgba(255,255,255,0.02);
    }}
    tr:last-child td {{ border-bottom: 0; }}
    tr.featured td {{ background: rgba(63,208,201,0.05); }}
    .up {{ color: var(--up); }}
    .down {{ color: var(--down); }}

    .split {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 18px;
    }}
    .block {{
      border: 1px solid var(--line); padding: 22px 20px; background: rgba(13,18,26,0.65);
    }}
    .block h4 {{ margin: 0 0 12px; font-size: 1.05rem; }}
    .block ul {{ margin: 0; padding: 0 18px 0 0; color: var(--muted); }}
    .block li {{ margin-bottom: 8px; }}
    .block li:last-child {{ margin-bottom: 0; }}

    .roadmap {{
      display: grid; gap: 1px; background: var(--line); border: 1px solid var(--line);
    }}
    .road {{
      display: grid; grid-template-columns: 140px 1fr; gap: 16px; align-items: center;
      background: var(--ink-2); padding: 18px 20px;
    }}
    .tag {{
      font-family: "Sora", sans-serif; font-size: 0.72rem; letter-spacing: 0.08em;
      text-align: center; padding: 8px 10px; border: 1px solid var(--line);
    }}
    .tag.done {{ color: var(--up); border-color: rgba(61,214,140,0.35); }}
    .tag.now {{ color: var(--accent); border-color: rgba(63,208,201,0.4); }}
    .tag.next {{ color: var(--muted); }}
    .road p {{ margin: 0; color: var(--muted); }}
    .road strong {{ color: var(--text); }}

    .disclaimer {{
      margin-top: 28px; padding: 16px 18px; border: 1px solid rgba(240,180,41,0.25);
      background: rgba(240,180,41,0.06); color: var(--muted); font-size: 0.88rem;
    }}
    .nav-toc {{
      display: flex; flex-wrap: wrap; gap: 8px; margin: 36px 0 8px;
    }}
    .nav-toc a {{
      text-decoration: none; color: var(--muted); font-size: 0.82rem;
      padding: 7px 12px; border: 1px solid var(--line); background: rgba(13,18,26,0.7);
      transition: color 0.2s ease, border-color 0.2s ease;
    }}
    .nav-toc a:hover {{ color: var(--accent); border-color: rgba(63,208,201,0.35); }}
    .chapter {{
      margin-top: 72px; padding-top: 28px; border-top: 1px solid var(--line);
    }}
    .chapter-head {{
      display: flex; flex-wrap: wrap; justify-content: space-between; gap: 12px;
      align-items: end; margin-bottom: 22px;
    }}
    .chapter-badge {{
      display: inline-block; padding: 6px 10px; border: 1px solid rgba(63,208,201,0.35);
      color: var(--accent); font-family: "Sora", sans-serif; font-size: 0.72rem;
      letter-spacing: 0.12em; margin-bottom: 10px;
    }}
    .chapter-head h2 {{
      margin: 0; font-size: clamp(1.7rem, 3vw, 2.2rem); font-weight: 800;
      letter-spacing: -0.02em; max-width: 16ch;
    }}
    .chapter-head p {{
      margin: 0; color: var(--muted); max-width: 28rem; font-size: 0.95rem;
    }}
    .hub-nav {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
      margin: 28px 0 8px;
    }}
    .hub-card {{
      display: block; text-decoration: none; color: inherit;
      border: 1px solid var(--line); background: rgba(13,18,26,0.75); padding: 18px 16px;
      transition: border-color 0.2s ease, transform 0.2s ease;
    }}
    .hub-card:hover {{ border-color: rgba(63,208,201,0.4); transform: translateY(-2px); }}
    .hub-card .n {{
      font-family: "Sora", sans-serif; color: var(--accent); font-size: 0.75rem;
      letter-spacing: 0.12em; margin-bottom: 8px;
    }}
    .hub-card strong {{ display: block; margin-bottom: 6px; font-size: 1.05rem; }}
    .hub-card p {{ margin: 0; color: var(--muted); font-size: 0.88rem; }}
    .result-cards {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 18px;
    }}
    .result-card {{
      border: 1px solid var(--line); background: rgba(13,18,26,0.7); padding: 16px;
    }}
    .result-card.featured {{
      border-color: rgba(63,208,201,0.4);
      background: linear-gradient(180deg, rgba(63,208,201,0.08), rgba(13,18,26,0.7));
    }}
    .result-top {{
      display: flex; justify-content: space-between; gap: 8px; align-items: baseline;
      margin-bottom: 10px;
    }}
    .result-top span {{ color: var(--muted); font-size: 0.78rem; }}
    .result-pnl {{
      font-family: "IBM Plex Mono", monospace; font-size: 1.45rem; font-weight: 600;
      direction: ltr; unicode-bidi: plaintext; margin-bottom: 12px;
    }}
    .result-grid {{
      display: grid; grid-template-columns: 1fr 1fr; gap: 8px;
    }}
    .result-grid div {{
      background: rgba(0,0,0,0.22); padding: 8px; text-align: center;
    }}
    .result-grid span {{ display: block; color: var(--muted); font-size: 0.72rem; }}
    .result-grid b {{ font-size: 0.92rem; }}
    .done-list {{
      display: grid; gap: 10px; margin: 0 0 18px;
    }}
    .done-item {{
      display: grid; grid-template-columns: 28px 1fr; gap: 12px; align-items: start;
      border: 1px solid var(--line); background: rgba(13,18,26,0.65); padding: 14px 16px;
    }}
    .done-item i {{
      color: var(--up); font-style: normal; font-weight: 700;
    }}
    .done-item p {{ margin: 0; color: var(--muted); }}
    .done-item strong {{ color: var(--text); }}
    .prose {{
      border: 1px solid var(--line); padding: 22px 20px; background: rgba(13,18,26,0.65);
      direction: rtl; text-align: right;
    }}
    .prose h3 {{
      margin: 0 0 14px; font-size: 1.35rem; font-weight: 800; color: var(--text);
    }}
    .prose h4 {{
      margin: 18px 0 8px; font-size: 1.05rem; font-weight: 700; color: var(--text);
    }}
    .prose p {{ margin: 0 0 14px; color: var(--muted); }}
    .prose p:last-child {{ margin-bottom: 0; }}
    .prose strong {{ color: var(--text); font-weight: 700; }}
    .prose ul, .prose ol {{
      margin: 0 0 8px; padding: 0 18px 0 0; color: var(--muted);
    }}
    .prose li {{ margin: 0 0 8px; }}
    .prose li:last-child {{ margin-bottom: 0; }}
    .callout {{
      margin-top: 14px; padding: 14px 16px;
      border: 1px solid rgba(63,208,201,0.25); background: rgba(63,208,201,0.06);
      color: var(--text); font-size: 0.95rem;
    }}
    .steps {{ display: grid; gap: 12px; }}
    .step {{
      display: grid; grid-template-columns: 52px 1fr; gap: 14px; align-items: start;
      border: 1px solid var(--line); background: rgba(13,18,26,0.65); padding: 16px;
    }}
    .step-no {{
      width: 42px; height: 42px; display: grid; place-items: center;
      border: 1px solid rgba(63,208,201,0.35); color: var(--accent);
      font-family: "Sora", sans-serif; font-weight: 700;
    }}
    .step h4 {{ margin: 0 0 6px; font-size: 1.02rem; }}
    .step p {{ margin: 0; color: var(--muted); font-size: 0.94rem; }}
    .glossary {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px;
    }}
    .term {{
      border: 1px solid var(--line); background: rgba(13,18,26,0.65); padding: 16px;
    }}
    .term h4 {{ margin: 0 0 8px; font-size: 0.95rem; color: var(--accent); }}
    .term p {{ margin: 0; color: var(--muted); font-size: 0.88rem; }}

    footer {{
      margin-top: 64px; padding-top: 24px; border-top: 1px solid var(--line);
      display: flex; justify-content: space-between; gap: 12px; flex-wrap: wrap;
      color: var(--muted); font-size: 0.82rem;
    }}
    footer .brand-en {{ color: var(--text); font-weight: 600; }}

    @keyframes fadeUp {{
      from {{ opacity: 0; transform: translateY(18px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}
    @keyframes chartRise {{
      from {{ opacity: 0; transform: translateY(24px) scale(1.02); }}
      to {{ opacity: 0.55; transform: translateY(0) scale(1); }}
    }}
    @keyframes pulse {{
      0% {{ box-shadow: 0 0 0 0 rgba(63,208,201,0.5); }}
      70% {{ box-shadow: 0 0 0 8px rgba(63,208,201,0); }}
      100% {{ box-shadow: 0 0 0 0 rgba(63,208,201,0); }}
    }}

    @media (max-width: 900px) {{
      .term-grid, .pillars, .pipeline, .kpi-strip, .split, .road, .hub-nav, .result-cards, .refresh-strip {{
        grid-template-columns: 1fr;
      }}
      .term-metrics {{ border-left: 0; border-top: 1px solid var(--line); }}
      .hero-brand {{ font-size: clamp(2.8rem, 16vw, 4.5rem); }}
      .hero {{ min-height: 92vh; }}
      .refresh-btn {{ width: 100%; }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="hero-bg" aria-hidden="true"></div>
    <div class="hero-chart" aria-hidden="true"></div>
    <div class="hero-grid" aria-hidden="true"></div>

    <div class="topbar">
      <div class="logo">
        <div class="mark" aria-hidden="true">AJV</div>
        <div class="logo-text">
          <strong>AJV</strong>
          <span>Amir · Javid · Vahid</span>
        </div>
      </div>
      <div class="status-pill" id="statusChip"><i></i> CONNECTING</div>
    </div>

    <div class="hero-content">
      <h1 class="hero-brand"><span>AMIR · JAVID · VAHID</span>AJV</h1>
      <p class="hero-line">
        پروژهٔ مشترک امیر، جاوید و وحید برای ساخت یک سیستم معاملاتی کریپتو
        که با قانون مشخص کار می‌کند — نه با حدس و هیجان.
      </p>
      <div class="cta-row">
        <a class="btn btn-primary" href="#ops">بخش عملیات</a>
        <a class="btn btn-ghost" href="#phase1">نتایج فاز ۱</a>
        <a class="btn btn-ghost" href="#learn">آموزش</a>
      </div>
    </div>
  </header>

  <div class="wrap">
    <nav class="hub-nav" aria-label="سه بخش اصلی">
      <a class="hub-card" href="#ops">
        <div class="n">01</div>
        <strong>عملیات زنده</strong>
        <p>قیمت، سیگنال، ساعت آپدیت و رفرش دستی</p>
      </a>
      <a class="hub-card" href="#phase1">
        <div class="n">02</div>
        <strong>فاز ۱ و نتایج</strong>
        <p>چه ساختیم، روی BTC/ETH/SOL چه شد</p>
      </a>
      <a class="hub-card" href="#learn">
        <div class="n">03</div>
        <strong>آموزش</strong>
        <p>منطق کار، واژه‌ها و مسیر بعدی</p>
      </a>
    </nav>

    <section class="chapter" id="intro">
      <div class="chapter-head">
        <div>
          <div class="chapter-badge">SECTION · INTRO</div>
          <h2>معرفی</h2>
        </div>
        <p>خلاصهٔ وضعیت فعلی پروژه، چیزهایی که آماده است، و مسیر بعدی.</p>
      </div>
      <div class="prose">
        <p>
          AJV الان در فاز ۱ تحقیقاتی است: سیستم قانون‌محور کریپتو روی BTCUSDT تایم‌فریم ۴ساعته،
          با بک‌تست و مانیتور فقط‌خواندنی. ساختار ۱۷بندی ICT/SMC در کد پیاده شده است.
          سفارش واقعی هنوز خاموش است.
        </p>
        <h4>وضعیت فعلی</h4>
        <ul>
          <li>هستهٔ Sweep/MSS + ICT (FVG/OB/OTE/PD) + Price Action (BOS/CHOCH) آماده است.</li>
          <li>امتیاز ۲۴تایی، No-Trade، Trade Management و فلسفهٔ معاملاتی کد شده‌اند.</li>
          <li>دموی عمومی روی GitHub Pages است و تقریباً هر ۲ ساعت با Actions آپدیت می‌شود.</li>
          <li>اسنپ‌شات زنده فقط‌خواندنی است؛ سفارش واقعی ارسال نمی‌شود.</li>
        </ul>
        <h4>چی آماده است</h4>
        <ul>
          <li>استراتژی کامل فاز ۱ با فیلترها و scoring</li>
          <li>بک‌تست با کارمزد، اسلیپیج، ریسک و مدیریت معامله</li>
          <li>اعتبارسنجی چندنماد و Walk-Forward</li>
          <li>Paper Trader فقط‌خواندنی</li>
          <li>اسناد: docs/AJV_STRUCTURE.md و docs/PHILOSOPHY.md</li>
        </ul>
        <h4>مسیر بعدی</h4>
        <ol>
          <li>مانیتور سیگنال‌های Paper بدون پول واقعی</li>
          <li>اگر کیفیت خوب بود، Demo/Testnet</li>
          <li>بعداً داشبورد، هشدار و اتصال امن‌تر به صرافی</li>
        </ol>
      </div>
    </section>

    <section class="chapter" id="ops">
      <div class="chapter-head">
        <div>
          <div class="chapter-badge">SECTION A · OPERATIONS</div>
          <h2>عملیات زنده پروژه</h2>
        </div>
        <p>این بخش فقط وضعیت فعلی بازار و سیستم را نشان می‌دهد. آموزش و جزئیات تحقیق این‌جا نیست.</p>
      </div>

    <section class="terminal" id="live" aria-live="polite">
      <div class="term-bar">
        <div>
          <h2>وضعیت زنده بازار</h2>
          <div class="term-meta">بیت‌کوین · چارت ۴ ساعته · همگام‌سازی خودکار هر ۲ ساعت</div>
        </div>
        <button type="button" class="refresh-btn" id="refreshBtn">به‌روزرسانی قیمت الان</button>
      </div>
      <div class="term-grid">
        <div class="signal-pane">
          <div class="label">سیگنال الان</div>
          <div class="state wait" id="signalState">در حال بررسی</div>
          <div class="detail" id="signalDetail">در حال خواندن آخرین وضعیت از بازار…</div>
        </div>
        <div class="term-metrics">
          <div class="metric"><span>قیمت زنده</span><b id="markPrice">—</b></div>
          <div class="metric"><span>آخرین قیمت بسته‌شده</span><b id="lastClose">—</b></div>
          <div class="metric"><span>منبع قیمت</span><b id="priceSource">—</b></div>
          <div class="metric"><span>حالت سیستم</span><b id="systemMode">فقط نمایش</b></div>
        </div>
      </div>
      <div class="refresh-strip">
        <div class="refresh-item">
          <span>ساعت آخرین به‌روزرسانی</span>
          <b id="updatedAt">—</b>
        </div>
        <div class="refresh-item">
          <span>مانده تا آپدیت بعدی خودکار</span>
          <b id="nextCountdown">—</b>
        </div>
        <p class="refresh-note">
          دکمه «به‌روزرسانی قیمت الان» قیمت لحظه‌ای را از منابع عمومی می‌گیرد
          (اگر بایننس در دسترس نباشد، از CoinGecko / Coinbase / Kraken استفاده می‌شود).
          آپدیت کامل سیگنال‌ها همچنان حدوداً هر ۲ ساعت از سرور می‌آید.
        </p>
      </div>
      <div class="term-foot">
        <span>این بخش فقط قیمت را می‌خواند. خرید و فروش واقعی انجام نمی‌شود.</span>
        <span class="badge" id="ordersBadge">سفارش خاموش</span>
      </div>
    </section>
    </section>

    <section class="chapter" id="phase1">
      <div class="chapter-head">
        <div>
          <div class="chapter-badge">SECTION B · PHASE 1</div>
          <h2>فاز ۱: چه کردیم و به چه نتیجه‌ای رسیدیم؟</h2>
        </div>
        <p>اینجا گزارش کار تیم است؛ نه آموزش ترید. تمرکز روی کارهای انجام‌شده و عددهای آزمایشی.</p>
      </div>

      <div class="prose" style="margin-bottom:22px">
        <p>
          <strong>AJV</strong> پروژهٔ مشترک <strong>Amir · Javid · Vahid</strong> است.
          در فاز ۱ هدف این بود که یک هستهٔ معاملاتی قانون‌محور بسازیم، روی دادهٔ گذشته تست کنیم،
          و ببینیم ایده اصلاً ارزش ادامه دارد یا نه — بدون معامله واقعی.
        </p>
      </div>

      <h3 class="sec-title" style="font-size:1.35rem; margin-top:8px">کارهای انجام‌شده در فاز ۱</h3>
      <div class="done-list">
        <div class="done-item"><i>✓</i><p><strong>موتور قوانین:</strong> تشخیص شکار نقدینگی، تغییر ساختار، و صدور سیگنال ورود/خروج</p></div>
        <div class="done-item"><i>✓</i><p><strong>بک‌تست:</strong> شبیه‌سازی معامله روی تاریخچه قیمت با کارمزد و لغزش واقعی‌تر</p></div>
        <div class="done-item"><i>✓</i><p><strong>مدیریت ریسک:</strong> ریسک ۱٪ در هر معامله، سقف ضرر روزانه، توقف بعد از ضررهای متوالی</p></div>
        <div class="done-item"><i>✓</i><p><strong>بررسی چند ارز مهم:</strong> بیت‌کوین، اتریوم و سولانا روی تایم‌فریم ۴ ساعته</p></div>
        <div class="done-item"><i>✓</i><p><strong>اعتبارسنجی زمانی:</strong> تست تکه‌تکه (Walk-Forward) برای بیت‌کوین</p></div>
        <div class="done-item"><i>✓</i><p><strong>مانیتور زنده فقط‌خواندنی:</strong> قیمت و سیگنال آزمایشی روی همین صفحه، بدون سفارش واقعی</p></div>
      </div>

      <h3 class="sec-title" id="results" style="font-size:1.35rem; margin-top:28px">نتایج آزمایشی</h3>
      <p class="sec-lead">
        فرض مشترک همه تست‌ها: شروع با ۱۰٬۰۰۰ تتر · چارت ۴ ساعته · با احتساب هزینه معامله.
        بازه بیت‌کوین: {btc_range}.
      </p>
      <div class="kpi-strip">
        <div class="kpi"><span>BTC · نتیجه اصلی</span><b class="{_pnl_class(btc['pnl']) if btc else ''}">{headline_pnl}</b></div>
        <div class="kpi"><span>ETH · بررسی مقایسه‌ای</span><b class="{_pnl_class(eth['pnl']) if eth else ''}">{eth_pnl}</b></div>
        <div class="kpi"><span>SOL · بررسی مقایسه‌ای</span><b class="{_pnl_class(sol['pnl']) if sol else ''}">{sol_pnl}</b></div>
        <div class="kpi"><span>BTC · سرمایه نهایی فرضی</span><b>{btc_equity}</b></div>
      </div>
      <div class="result-cards">
        {asset_cards if asset_cards else "<p class='sec-lead'>داده نتایج محلی موجود نیست.</p>"}
      </div>
      <div class="prose">
        <p>
          جمع‌بندی فاز ۱: روی <strong>بیت‌کوین</strong> نتیجه امیدوارکننده‌تر بوده
          (حدود {headline_pnl} سود آزمایشی، درصد برد حدود {headline_wr}، قدرت سود {headline_pf}).
          روی <strong>اتریوم</strong> و <strong>سولانا</strong> هم بررسی کرده‌ایم تا فقط به یک ارز وابسته نباشیم؛
          ولی نتیجه روی همه یکسان نیست. فعلاً بیت‌کوین بهتر از بقیه جواب داده.
        </p>
        <div class="callout">
          مهم: این عددها آزمایش روی گذشته‌اند، نه سود واقعی در حساب صرافی.
        </div>
      </div>

      <h3 class="sec-title" id="validation" style="font-size:1.35rem; margin-top:28px">پایداری نتیجه روی بیت‌کوین</h3>
      <p class="sec-lead">
        تاریخ را تکه‌تکه کرده‌ایم (حدود ۹۰ روزه) تا ببینیم نتیجه فقط شانس یک دوره نبوده.
        فعلاً {positive_folds} از {total_folds} تکه مثبت شده.
      </p>
      <div class="table-shell">
        <table>
          <thead>
            <tr><th>بازه زمانی</th><th>تعداد معامله</th><th>درصد برد</th><th>سود/زیان</th><th>قدرت سود</th></tr>
          </thead>
          <tbody>
            {wf_rows if wf_rows else "<tr><td colspan='5'>داده walk-forward موجود نیست</td></tr>"}
          </tbody>
        </table>
      </div>

      <h3 class="sec-title" style="font-size:1.35rem; margin-top:28px">جزئیات عددی همه ارزها</h3>
      <div class="table-shell">
        <table>
          <thead>
            <tr>
              <th>ارز</th><th>سود/زیان</th><th>درصد برد</th><th>تعداد معامله</th><th>قدرت سود</th><th>بیشترین افت</th><th>سرمایه نهایی</th>
            </tr>
          </thead>
          <tbody>
            {asset_rows if asset_rows else "<tr><td colspan='7'>داده بک‌تست محلی موجود نیست</td></tr>"}
          </tbody>
        </table>
      </div>

      <div class="split" style="margin-top:22px">
        <div class="block">
          <h4>در فاز ۱ انجام شد</h4>
          <ul>
            <li>ساخت هسته قوانین و بک‌تست</li>
            <li>بررسی BTC + ETH + SOL</li>
            <li>ریسک و هزینه معامله</li>
            <li>مانیتور زنده فقط‌خواندنی</li>
          </ul>
        </div>
        <div class="block">
          <h4>عمداً انجام نشد</h4>
          <ul>
            <li>خرید و فروش واقعی</li>
            <li>تضمین سود</li>
            <li>ادعای آماده‌بودن برای همه ارزها</li>
            <li>محصول نهایی کاربرپسند کامل</li>
          </ul>
        </div>
      </div>
    </section>

    <section class="chapter" id="learn">
      <div class="chapter-head">
        <div>
          <div class="chapter-badge">SECTION C · LEARN</div>
          <h2>آموزش: سیستم چطور فکر می‌کند؟</h2>
        </div>
        <p>اگر تازه واردی و می‌خواهی منطق کار را بفهمی، این بخش برای توست. از نتایج فاز ۱ جداست.</p>
      </div>

      <h3 class="sec-title" style="font-size:1.35rem">چک‌لیست ۴ مرحله‌ای ورود</h3>
      <p class="sec-lead">اگر حتی یک مرحله برقرار نباشد، سیستم وارد معامله نمی‌شود.</p>
      <div class="pipeline" style="margin-bottom:18px">
        <div class="pipe">
          <div class="n">01</div>
          <h4>تله قیمت</h4>
          <p>قیمت یک لحظه از سقف یا کف مهم رد می‌شود و سریع برمی‌گردد.</p>
        </div>
        <div class="pipe">
          <div class="n">02</div>
          <h4>تأیید جهت</h4>
          <p>ساختار چارت می‌شکند؛ احتمال عوض شدن جهت بالاتر می‌رود.</p>
        </div>
        <div class="pipe">
          <div class="n">03</div>
          <h4>ورود کنترل‌شده</h4>
          <p>حد ضرر مشخص؛ هدف سود حدود ۲ برابر ریسک؛ حجم با ۱٪ حساب.</p>
        </div>
        <div class="pipe">
          <div class="n">04</div>
          <h4>فیلتر نهایی</h4>
          <p>فقط اگر جهت روزانه و ساعت بازار مناسب باشد.</p>
        </div>
      </div>
      <div class="steps">
        <div class="step">
          <div class="step-no">۱</div>
          <div>
            <h4>شکار نقدینگی</h4>
            <p>گاهی بازار برای فعال‌کردن سفارش‌های پشت یک سقف/کف، یک لحظه از آن رد می‌شود و برمی‌گردد. سیستم دنبال همین حرکت است.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۲</div>
          <div>
            <h4>تأیید تغییر جهت</h4>
            <p>برگشت به‌تنهایی کافی نیست؛ باید ساختار قبلی چارت هم بشکند.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۳</div>
          <div>
            <h4>ورود با سقف ضرر</h4>
            <p>حد ضرر پشت همان نقطه گذاشته می‌شود تا اگر اشتباه بود، ضرر بزرگ نشود.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۴</div>
          <div>
            <h4>فیلتر کیفیت</h4>
            <p>اگر جهت روزانه مخالف باشد یا چند ضرر پشت‌سرهم خورده باشد، دست نگه می‌دارد.</p>
          </div>
        </div>
      </div>

      <h3 class="sec-title" id="words" style="font-size:1.35rem; margin-top:28px">معنی واژه‌ها</h3>
      <div class="glossary">
        <div class="term"><h4>بک‌تست</h4><p>امتحان استراتژی روی قیمت‌های گذشته.</p></div>
        <div class="term"><h4>سیگنال</h4><p>یعنی شرایط ورود از نظر قوانین سیستم برقرار است.</p></div>
        <div class="term"><h4>حد ضرر</h4><p>خط قرمز خروج برای اینکه ضرر بزرگ نشود.</p></div>
        <div class="term"><h4>حد سود</h4><p>هدف قیمتی برای بستن معامله با سود.</p></div>
        <div class="term"><h4>درصد برد</h4><p>از هر ۱۰۰ معامله، چندتایش سود بوده.</p></div>
        <div class="term"><h4>بیشترین افت</h4><p>بدترین افت سرمایه از قله تا دره در طول آزمایش.</p></div>
        <div class="term"><h4>قدرت سود</h4><p>جمع سودها ÷ جمع ضررها. بالای ۱ یعنی سود کل بیشتر بوده.</p></div>
        <div class="term"><h4>Paper</h4><p>تمرین با بازار واقعی، بدون پول واقعی.</p></div>
      </div>

      <h3 class="sec-title" id="roadmap" style="font-size:1.35rem; margin-top:28px">مسیر بعدی</h3>
      <div class="roadmap">
        <div class="road">
          <div class="tag done">انجام شده</div>
          <p><strong>فاز ۱:</strong> هسته قوانین، تست روی BTC/ETH/SOL، ریسک، مانیتور زنده</p>
        </div>
        <div class="road">
          <div class="tag now">الان</div>
          <p><strong>رصد آزمایشی:</strong> نگاه به سیگنال‌ها بدون پول واقعی</p>
        </div>
        <div class="road">
          <div class="tag next">بعدی</div>
          <p><strong>حساب تست:</strong> اگر کیفیت خوب بود، سفارش آزمایشی روی دمو</p>
        </div>
        <div class="road">
          <div class="tag next">آینده</div>
          <p><strong>نسخه جدی‌تر:</strong> فقط اگر آمار پایدار بود</p>
        </div>
      </div>
      <div class="disclaimer">
        این صفحه توصیه سرمایه‌گذاری نیست.
        فقط نشان می‌دهد تیم <strong>AJV</strong> در فاز ۱ چه کرده و به چه نتایج آزمایشی رسیده است.
        حالت فعلی: فقط‌خواندنی — سفارش واقعی ارسال نمی‌شود.
      </div>
    </section>

    <footer>
      <div><span class="brand-en">AJV</span> · Amir · Javid · Vahid</div>
      <div>Phase 1 · Read-only · No live orders</div>
    </footer>
  </div>

  <script>
    // Binance is often 451 from Iran browsers; use public fallbacks first.
    const PRICE_SOURCES = [
      {{
        name: 'CoinGecko',
        url: 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd',
        parse: (data) => Number(data && data.bitcoin && data.bitcoin.usd),
      }},
      {{
        name: 'Coinbase',
        url: 'https://api.coinbase.com/v2/prices/BTC-USD/spot',
        parse: (data) => Number(data && data.data && data.data.amount),
      }},
      {{
        name: 'Kraken',
        url: 'https://api.kraken.com/0/public/Ticker?pair=XBTUSD',
        parse: (data) => Number(data && data.result && (data.result.XXBTZUSD || data.result.XBTUSD) && (data.result.XXBTZUSD || data.result.XBTUSD).c[0]),
      }},
      {{
        name: 'Binance Vision',
        url: 'https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT',
        parse: (data) => Number(data && data.price),
      }},
    ];
    let priceState = {{ value: null, at: 0, source: '—' }};

    function fmtPrice(v) {{
      return Number(v).toLocaleString('en-US', {{ maximumFractionDigits: 2 }}) + ' USDT';
    }}

    function setPrice(value, atMs, source) {{
      if (priceState.at && atMs < priceState.at) return;
      priceState = {{ value, at: atMs, source }};
      document.getElementById('markPrice').textContent = fmtPrice(value);
      document.getElementById('priceSource').textContent = source;
      document.getElementById('updatedAt').textContent = new Date(atMs).toLocaleString('fa-IR');
    }}

    function getNextScheduledUpdate(now) {{
      const t = new Date(now.getTime());
      t.setUTCSeconds(0, 0);
      t.setUTCMilliseconds(0);
      t.setUTCMinutes(17);
      if (t <= now) {{
        t.setUTCHours(t.getUTCHours() + 1);
        t.setUTCMinutes(17);
      }}
      while (t.getUTCHours() % 2 !== 0) {{
        t.setUTCHours(t.getUTCHours() + 1);
        t.setUTCMinutes(17);
      }}
      return t;
    }}

    function fmtCountdown(ms) {{
      if (ms < 0) ms = 0;
      const total = Math.floor(ms / 1000);
      const h = String(Math.floor(total / 3600)).padStart(2, '0');
      const m = String(Math.floor((total % 3600) / 60)).padStart(2, '0');
      const s = String(total % 60).padStart(2, '0');
      return h + ':' + m + ':' + s;
    }}

    function tickCountdown() {{
      const el = document.getElementById('nextCountdown');
      const next = getNextScheduledUpdate(new Date());
      el.textContent = fmtCountdown(next - Date.now());
      el.title = 'آپدیت بعدی حدوداً: ' + next.toLocaleString('fa-IR');
    }}

    async function loadLive() {{
      const chip = document.getElementById('statusChip');
      const state = document.getElementById('signalState');
      const detail = document.getElementById('signalDetail');
      try {{
        const res = await fetch('./live.json?ts=' + Date.now(), {{ cache: 'no-store' }});
        if (!res.ok) throw new Error('missing');
        const data = await res.json();
        chip.innerHTML = '<i></i> آنلاین · وصل به بازار';
        const serverAt = new Date(data.updated_at_utc).getTime();
        setPrice(Number(data.mark_price), serverAt, 'سرور · خودکار');
        document.getElementById('lastClose').textContent = fmtPrice(data.last_close);
        document.getElementById('systemMode').textContent = data.orders_enabled ? 'معامله واقعی' : 'فقط نمایش';
        document.getElementById('ordersBadge').textContent = data.orders_enabled ? 'سفارش روشن' : 'سفارش خاموش';
        if (data.active_signal) {{
          const s = data.active_signal;
          const sideFa = s.side === 'long' ? 'خرید' : 'فروش';
          state.className = 'state hot';
          state.textContent = 'سیگنال فعال: ' + sideFa;
          detail.textContent = 'ورود ' + s.entry + '  ·  حد ضرر ' + s.stop_loss + '  ·  حد سود ' + s.take_profit;
        }} else {{
          state.className = 'state wait';
          state.textContent = 'الان سیگنال فعالی نیست';
          detail.textContent = 'سیستم آنلاین است و منتظر شرایط بعدی می‌ماند';
        }}
      }} catch (e) {{
        chip.innerHTML = '<i></i> در انتظار آپدیت';
        state.className = 'state wait';
        state.textContent = 'هنوز داده زنده نیامده';
        detail.textContent = 'بعد از اولین آپدیت خودکار، اینجا قیمت و وضعیت نشان داده می‌شود.';
      }}
    }}

    async function refreshPriceNow() {{
      const btn = document.getElementById('refreshBtn');
      btn.disabled = true;
      btn.textContent = 'در حال دریافت...';
      try {{
        let price = null;
        let sourceName = null;
        let lastErr = null;
        for (const src of PRICE_SOURCES) {{
          try {{
            const res = await fetch(src.url, {{ cache: 'no-store' }});
            if (!res.ok) throw new Error(src.name + ' HTTP ' + res.status);
            const data = await res.json();
            const value = src.parse(data);
            if (!Number.isFinite(value) || value <= 0) throw new Error(src.name + ' bad price');
            price = value;
            sourceName = src.name;
            break;
          }} catch (err) {{
            lastErr = err;
          }}
        }}
        if (price == null) throw lastErr || new Error('price fetch failed');
        setPrice(price, Date.now(), sourceName + ' · دستی');
        document.getElementById('statusChip').innerHTML = '<i></i> آنلاین · قیمت دستی تازه‌شد';
      }} catch (err) {{
        document.getElementById('priceSource').textContent = 'خطا در رفرش';
        alert('نتوانستیم قیمت لحظه‌ای را بگیریم. چند منبع عمومی را هم امتحان کردیم.');
      }} finally {{
        btn.disabled = false;
        btn.textContent = 'به‌روزرسانی قیمت الان';
      }}
    }}

    document.getElementById('refreshBtn').addEventListener('click', refreshPriceNow);
    loadLive();
    tickCountdown();
    setInterval(loadLive, 60 * 1000);
    setInterval(tickCountdown, 1000);
  </script>
</body>
</html>
"""

    out_share = Path("share") / "index.html"
    out_docs = Path("docs") / "index.html"
    out_share.parent.mkdir(parents=True, exist_ok=True)
    out_docs.parent.mkdir(parents=True, exist_ok=True)
    out_share.write_text(html, encoding="utf-8")
    out_docs.write_text(html, encoding="utf-8")
    (Path("docs") / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote product demo -> {out_share.resolve()}")
    print(f"Wrote GitHub Pages demo -> {out_docs.resolve()}")


if __name__ == "__main__":
    main()
