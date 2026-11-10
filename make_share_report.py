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
    asset_rows = ""
    for a in assets:
        featured = " featured" if a["name"] == "BTC" else ""
        asset_rows += f"""
        <tr class="{featured.strip()}">
          <td><strong>{a['name']}</strong><span class="muted"> /USDT · 4H</span></td>
          <td class="mono {_pnl_class(a['pnl'])}">{a['pnl']:+,.2f}</td>
          <td class="mono">{a['win_rate']:.1f}%</td>
          <td class="mono">{a['trades']}</td>
          <td class="mono">{_pf(a['pf'])}</td>
          <td class="mono">{a['mdd']:.2f}%</td>
          <td class="mono">{a['equity']:,.0f}</td>
        </tr>
        """

    headline_pnl = f"{btc['pnl']:+,.0f}" if btc else "—"
    headline_wr = f"{btc['win_rate']:.0f}%" if btc else "—"
    headline_pf = _pf(btc["pf"]) if btc else "—"
    btc_equity = f"{btc['equity']:,.0f}" if btc else "—"
    btc_range = f"{btc['start']} → {btc['end']}" if btc else "—"

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
    .simple-box {{
      margin-top: 28px; border: 1px solid rgba(63,208,201,0.28);
      background: rgba(63,208,201,0.05); padding: 22px 20px;
    }}
    .simple-box h3 {{
      margin: 0 0 14px; font-size: 1.2rem;
    }}
    .simple-grid {{
      display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
    }}
    .simple-item {{
      background: rgba(7,9,13,0.45); border: 1px solid var(--line); padding: 14px;
    }}
    .simple-item strong {{
      display: block; margin-bottom: 6px; color: var(--accent); font-size: 0.92rem;
    }}
    .simple-item p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
    .prose {{
      border: 1px solid var(--line); padding: 22px 20px; background: rgba(13,18,26,0.65);
    }}
    .prose p {{ margin: 0 0 14px; color: var(--muted); }}
    .prose p:last-child {{ margin-bottom: 0; }}
    .prose strong {{ color: var(--text); font-weight: 700; }}
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
      .term-grid, .pillars, .pipeline, .kpi-strip, .split, .road, .simple-grid, .refresh-strip {{
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
        <a class="btn btn-primary" href="#live">وضعیت زنده بازار</a>
        <a class="btn btn-ghost" href="#why">این پروژه چیست؟</a>
      </div>
    </div>
  </header>

  <div class="wrap">
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
          دکمه «به‌روزرسانی قیمت الان» قیمت لحظه‌ای را مستقیم از بایننس می‌گیرد.
          آپدیت کامل سیگنال‌ها همچنان حدوداً هر ۲ ساعت از سرور می‌آید.
        </p>
      </div>
      <div class="term-foot">
        <span>این بخش فقط قیمت را می‌خواند. خرید و فروش واقعی انجام نمی‌شود.</span>
        <span class="badge" id="ordersBadge">سفارش خاموش</span>
      </div>
    </section>

    <section class="simple-box" id="simple">
      <h3>اگر هیچی از ترید بلد نیستی، همین ۳ خط کافی است</h3>
      <div class="simple-grid">
        <div class="simple-item">
          <strong>۱) این چیه؟</strong>
          <p>یک پروژه آزمایشی برای ساخت ربات معامله‌گر با قانون مشخص — نه با حدس شخصی.</p>
        </div>
        <div class="simple-item">
          <strong>۲) الان چه کار می‌کند؟</strong>
          <p>روی داده‌های گذشته تست شده و قیمت زنده را نشان می‌دهد. هنوز پول واقعی جابه‌جا نمی‌کند.</p>
        </div>
        <div class="simple-item">
          <strong>۳) نتیجه اولیه؟</strong>
          <p>روی بیت‌کوین امیدوارکننده بوده، روی بعضی ارزها ضعیف‌تر. هنوز قطعی نیست.</p>
        </div>
      </div>
    </section>

    <nav class="nav-toc" aria-label="فهرست">
      <a href="#simple">خلاصه ساده</a>
      <a href="#why">این پروژه چیست؟</a>
      <a href="#scope">الان چه می‌کند؟</a>
      <a href="#method">چطور کار می‌کند؟</a>
      <a href="#built">چه ساخته شده؟</a>
      <a href="#results">نتایج</a>
      <a href="#validation">چقدر پایدار است؟</a>
      <a href="#not">چه چیزی نیست؟</a>
      <a href="#words">معنی واژه‌ها</a>
      <a href="#roadmap">بعدش چی؟</a>
    </nav>

    <section id="why">
      <div class="sec-kicker">PURPOSE</div>
      <h3 class="sec-title">AJV چیست؟</h3>
      <div class="prose">
        <p>
          <strong>AJV</strong> مخفف اسم سه نفر تیم است: <strong>Amir · Javid · Vahid</strong>.
          هدف‌شان ساخت یک سیستم معاملاتی است که فقط وقتی وارد شود که <strong>قانون از قبل نوشته‌شده</strong> برقرار باشد؛
          نه وقتی حال کسی خوب است یا از ضرر قبلی عصبانی است.
        </p>
        <p>
          مسیر کار ساده است: اول منطق را روی داده‌های گذشته بازار تست می‌کنیم.
          اگر نتیجه پایدار بود، بعداً به حالت آزمایشی (بدون پول واقعی) می‌رویم.
          معامله واقعی فقط وقتی مطرح می‌شود که آمار واقعاً قابل‌اتکا باشد.
        </p>
        <p>
          الان <strong>فاز ۱</strong> است: تحقیق و آزمایش. پول واقعی در صرافی نیست.
          این صفحه آنلاین است و حدوداً هر ۲ ساعت قیمت بازار را می‌خواند،
          ولی فقط برای نمایش وضعیت — <strong>سفارش واقعی ارسال نمی‌شود</strong>.
        </p>
        <div class="callout">
          مثل تست موتور روی میز کارگاه: هنوز وارد خیابان نشده‌ایم.
        </div>
      </div>
    </section>

    <section id="scope">
      <div class="sec-kicker">SCOPE</div>
      <h3 class="sec-title">الان دقیقاً چه کار می‌کند؟</h3>
      <p class="sec-lead">مرز فاز ۱ را شفاف بگوییم: چه چیزی هست و چه چیزی هنوز نیست.</p>
      <div class="split">
        <div class="block">
          <h4>الان فعال است</h4>
          <ul>
            <li><strong>بازار:</strong> کریپتو — تمرکز اصلی روی بیت‌کوین</li>
            <li><strong>چارت:</strong> کندل ۴ ساعته</li>
            <li><strong>روش:</strong> قانون‌محور (نه هوش مصنوعی پیش‌بینی‌کننده)</li>
            <li><strong>خروجی:</strong> سیگنال آزمایشی + نتیجه بک‌تست</li>
            <li><strong>صرافی:</strong> فقط خواندن قیمت</li>
            <li><strong>آپدیت صفحه:</strong> حدوداً هر ۲ ساعت</li>
          </ul>
        </div>
        <div class="block">
          <h4>الان انجام نمی‌دهد</h4>
          <ul>
            <li>خرید و فروش واقعی در صرافی</li>
            <li>وعده یا تضمین سود</li>
            <li>ادعای اینکه روی همه ارزها عالی کار می‌کند</li>
            <li>اپ موبایل یا هشدار کامل</li>
          </ul>
        </div>
      </div>
      <div class="pillars" style="margin-top:18px">
        <div class="pillar">
          <strong>موتور قوانین</strong>
          <p>فقط وقتی همه شرط‌های ورود برقرار باشد، می‌گوید «الان می‌شود وارد شد».</p>
        </div>
        <div class="pillar">
          <strong>مدیریت ریسک</strong>
          <p>در هر معامله حداکثر ۱٪ کل پول ریسک می‌شود. اگر روز بد باشد، دست نگه می‌دارد.</p>
        </div>
        <div class="pillar">
          <strong>نمایش زنده</strong>
          <p>قیمت بازار را می‌بیند و سیگنال آزمایشی را نشان می‌دهد؛ بدون خرید و فروش واقعی.</p>
        </div>
      </div>
    </section>

    <section id="method">
      <div class="sec-kicker">METHOD</div>
      <h3 class="sec-title">چطور تصمیم می‌گیرد؟</h3>
      <p class="sec-lead">
        فکر کن یک چک‌لیست ۴ مرحله‌ای است. اگر حتی یک مرحله رد شود، وارد معامله نمی‌شود.
      </p>
      <div class="pipeline" style="margin-bottom:18px">
        <div class="pipe">
          <div class="n">01</div>
          <h4>تله قیمت</h4>
          <p>قیمت یک لحظه از سقف یا کف مهم رد می‌شود و سریع برمی‌گردد.</p>
        </div>
        <div class="pipe">
          <div class="n">02</div>
          <h4>تأیید جهت</h4>
          <p>بعدش ساختار چارت می‌شکند؛ یعنی احتمال عوض شدن جهت بالاتر می‌رود.</p>
        </div>
        <div class="pipe">
          <div class="n">03</div>
          <h4>ورود امن‌تر</h4>
          <p>حد ضرر مشخص می‌گذارد و هدف سود حدود ۲ برابر همان ریسک است.</p>
        </div>
        <div class="pipe">
          <div class="n">04</div>
          <h4>فیلتر نهایی</h4>
          <p>اگر ساعت بازار یا جهت روزانه مناسب نباشد، وارد نمی‌شود.</p>
        </div>
      </div>
      <div class="steps">
        <div class="step">
          <div class="step-no">۱</div>
          <div>
            <h4>شکار نقدینگی</h4>
            <p>بازار گاهی برای فعال‌کردن سفارش‌های پشت یک سقف یا کف، یک لحظه از آن رد می‌شود و سریع برمی‌گردد.
            سیستم دنبال همین حرکت است.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۲</div>
          <div>
            <h4>تأیید تغییر جهت</h4>
            <p>برگشت کافی نیست. باید ساختار قبلی چارت هم بشکند تا سیستم بگوید «احتمال تغییر جهت بالاست».</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۳</div>
          <div>
            <h4>ورود با سقف ضرر مشخص</h4>
            <p>حد ضرر پشت همان نقطهٔ شکار نقدینگی گذاشته می‌شود. هدف سود حدود ۲ برابر همان ریسک است.
            اگر اشتباه باشد، فقط بخش کوچکی از حساب آسیب می‌بیند.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۴</div>
          <div>
            <h4>فیلتر کیفیت</h4>
            <p>اگر جهت روزانه مخالف باشد، یا سشن مناسب نباشد، یا چند ضرر پشت‌سرهم خورده باشد،
            سیستم دست نگه می‌دارد.</p>
          </div>
        </div>
      </div>
    </section>

    <section id="built">
      <div class="sec-kicker">BUILD</div>
      <h3 class="sec-title">تا اینجا چه ساخته‌ایم؟</h3>
      <div class="prose">
        <p><strong>۱. موتور استراتژی:</strong> سقف/کف مهم، شکار نقدینگی، تغییر ساختار و صدور سیگنال را تشخیص می‌دهد.</p>
        <p><strong>۲. بک‌تست:</strong> روی تاریخچه قیمت، معامله‌ها را شبیه‌سازی می‌کند و سود/زیان را حساب می‌کند.</p>
        <p><strong>۳. ریسک:</strong> سقف ضرر روزانه، توقف بعد از ضررهای متوالی، و احتساب کارمزد/لغزش قیمت.</p>
        <p><strong>۴. اعتبارسنجی:</strong> تست روی BTC / ETH / SOL و تست تکه‌تکه زمانی (Walk-Forward).</p>
        <p><strong>۵. Paper:</strong> قیمت زنده را می‌خواند و فقط می‌گوید سیگنال هست یا نه.</p>
        <p><strong>۶. این صفحه:</strong> دموی عمومی AJV برای دیدن وضعیت زنده و توضیح کامل پروژه.</p>
      </div>
    </section>

    <section id="results">
      <div class="sec-kicker">BACKTEST</div>
      <h3 class="sec-title">نتیجه آزمایش روی گذشته</h3>
      <p class="sec-lead">
        فرض: شروع با ۱۰٬۰۰۰ تتر · تایم‌فریم ۴ ساعته · با احتساب کارمزد و لغزش.
        بازه بیت‌کوین: {btc_range}. سبز = سود آزمایشی، قرمز = زیان آزمایشی.
      </p>
      <div class="kpi-strip">
        <div class="kpi"><span>سود/زیان آزمایشی BTC</span><b class="{_pnl_class(btc['pnl']) if btc else ''}">{headline_pnl}</b></div>
        <div class="kpi"><span>چند درصد معامله‌ها سود شد</span><b>{headline_wr}</b></div>
        <div class="kpi"><span>نسبت کل سود به کل ضرر</span><b>{headline_pf}</b></div>
        <div class="kpi"><span>سرمایه نهایی فرضی</span><b>{btc_equity}</b></div>
      </div>
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
      <div class="prose" style="margin-top:16px">
        <p>
          روی <strong>بیت‌کوین</strong> بهتر جواب داده: حدود {headline_pnl} سود آزمایشی و سرمایه نهایی حدود {btc_equity}.
          روی اتریوم ضعیف‌تر است. پس این منطق هنوز برای همه ارزها ثابت نشده و باید محتاط باشیم.
        </p>
      </div>
    </section>

    <section id="validation">
      <div class="sec-kicker">VALIDATION</div>
      <h3 class="sec-title">آیا نتیجه فقط شانس یک دوره بود؟</h3>
      <p class="sec-lead">
        تاریخ را تکه‌تکه کرده‌ایم (حدود ۹۰ روزه) تا ببینیم نتیجه پایدار است یا نه.
        فعلاً {positive_folds} از {total_folds} تکه مثبت شده — امیدوارکننده است، ولی هنوز کامل یکدست نیست.
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
    </section>

    <section id="not">
      <div class="sec-kicker">LIMITS</div>
      <h3 class="sec-title">صریح بگوییم چه چیزی نیست</h3>
      <div class="prose">
        <p><strong>تضمین سود نیست.</strong> آینده بازار را کسی قطعی نمی‌داند.</p>
        <p><strong>ربات پول‌ساز زنده نیست.</strong> هنوز چیزی در صرافی نمی‌خرد و نمی‌فروشد.</p>
        <p><strong>محصول نهایی نیست.</strong> هنوز فاز تحقیق و ساخت هسته است.</p>
        <p><strong>برای همه ارزها اثبات نشده.</strong> فعلاً بیت‌کوین بهتر از بقیه بوده.</p>
      </div>
    </section>

    <section id="words">
      <div class="sec-kicker">WORDS</div>
      <h3 class="sec-title">معنی واژه‌های سخت</h3>
      <p class="sec-lead">اگر جایی اصطلاحی دیدی و نفهمیدی، همین‌جا معنیش هست.</p>
      <div class="glossary">
        <div class="term"><h4>بک‌تست</h4><p>امتحان استراتژی روی قیمت‌های گذشته، مثل بازپخش فیلم بازی‌های قبلی.</p></div>
        <div class="term"><h4>سیگنال</h4><p>پیامی که می‌گوید الان شرایط ورود به معامله از نظر قوانین سیستم برقرار است.</p></div>
        <div class="term"><h4>حد ضرر (SL)</h4><p>خط قرمز خروج؛ اگر قیمت به آنجا برسد معامله بسته می‌شود تا ضرر بزرگ نشود.</p></div>
        <div class="term"><h4>حد سود (TP)</h4><p>هدف قیمتی برای بستن معامله با سود.</p></div>
        <div class="term"><h4>Win Rate</h4><p>از هر ۱۰۰ معامله، چندتایش سود بوده.</p></div>
        <div class="term"><h4>Max Drawdown</h4><p>بیشترین افت سرمایه از قله تا دره در طول آزمایش.</p></div>
        <div class="term"><h4>Profit Factor</h4><p>جمع سودها تقسیم بر جمع ضررها. بالاتر از ۱ یعنی سود کل بیشتر از ضرر کل بوده.</p></div>
        <div class="term"><h4>Paper Trading</h4><p>تمرین با سیگنال واقعی بازار، بدون گذاشتن پول واقعی.</p></div>
        <div class="term"><h4>Rule-based</h4><p>سیستم فقط وقتی عمل می‌کند که قانون از قبل نوشته‌شده برقرار باشد؛ نه با حس شخصی.</p></div>
        <div class="term"><h4>Walk-Forward</h4><p>تست تکه‌تکه روی بازه‌های زمانی مختلف، برای اینکه ببینیم نتیجه اتفاقی یک دوره نبوده.</p></div>
      </div>
    </section>

    <section id="roadmap">
      <div class="sec-kicker">NEXT</div>
      <h3 class="sec-title">بعدش چی؟</h3>
      <div class="roadmap">
        <div class="road">
          <div class="tag done">انجام شده</div>
          <p><strong>فاز ۱:</strong> ساخت هسته قوانین، تست روی گذشته، مدیریت ریسک، و این صفحه معرفی</p>
        </div>
        <div class="road">
          <div class="tag now">الان</div>
          <p><strong>رصد آزمایشی:</strong> چند روز سیگنال‌ها را بدون پول واقعی نگاه می‌کنیم</p>
        </div>
        <div class="road">
          <div class="tag next">بعدی</div>
          <p><strong>حساب تست:</strong> اگر کیفیت خوب بود، سفارش آزمایشی روی حساب دمو (هنوز بدون پول واقعی)</p>
        </div>
        <div class="road">
          <div class="tag next">آینده</div>
          <p><strong>نسخه جدی‌تر:</strong> فقط اگر آمار پایدار بود — داشبورد، هشدار، و اتصال امن‌تر</p>
        </div>
      </div>
      <div class="disclaimer">
        این صفحه توصیه سرمایه‌گذاری نیست و تضمین سود نمی‌دهد.
        فقط وضعیت پروژه <strong>AJV</strong> (Amir · Javid · Vahid) را نشان می‌دهد:
        چه ساخته شده، الان کجا هستیم، و نتیجه آزمایش اولیه چه بوده است.
        حالت فعلی: فقط‌خواندنی — سفارش واقعی ارسال نمی‌شود.
      </div>
    </section>

    <footer>
      <div><span class="brand-en">AJV</span> · Amir · Javid · Vahid</div>
      <div>Phase 1 · Read-only · No live orders</div>
    </footer>
  </div>

  <script>
    const PRICE_URLS = [
      'https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCUSDT',
      'https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT',
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
        let lastErr = null;
        for (const url of PRICE_URLS) {{
          try {{
            const res = await fetch(url, {{ cache: 'no-store' }});
            if (!res.ok) throw new Error('HTTP ' + res.status);
            const data = await res.json();
            price = Number(data.price);
            if (!Number.isFinite(price)) throw new Error('bad price');
            break;
          }} catch (err) {{
            lastErr = err;
          }}
        }}
        if (price == null) throw lastErr || new Error('price fetch failed');
        setPrice(price, Date.now(), 'بایننس · دستی');
        document.getElementById('statusChip').innerHTML = '<i></i> آنلاین · قیمت دستی تازه‌شد';
      }} catch (err) {{
        document.getElementById('priceSource').textContent = 'خطا در رفرش';
        alert('نتوانستیم قیمت لحظه‌ای را بگیریم. اینترنت یا دسترسی به بایننس را چک کن.');
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
