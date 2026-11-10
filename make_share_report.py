"""
Build a beginner-friendly, self-contained HTML report for sharing Phase 1.
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
    asset_cards = ""
    name_fa = {"BTC": "بیت‌کوین", "ETH": "اتریوم", "SOL": "سولانا"}
    for i, a in enumerate(assets):
        featured = " featured" if a["name"] == "BTC" else ""
        delay = 0.08 + i * 0.06
        fa = name_fa.get(a["name"], a["name"])
        asset_cards += f"""
        <article class="asset-card{featured}" style="animation-delay:{delay:.2f}s">
          <div class="asset-top">
            <div>
              <div class="asset-name">{a['name']}<span>/USDT</span></div>
              <div class="asset-range">{fa} · {a['start']} تا {a['end']}</div>
            </div>
            <div class="asset-badge">۴ ساعته</div>
          </div>
          <div class="asset-pnl {_pnl_class(a['pnl'])}">{a['pnl']:+,.2f} USDT</div>
          <div class="asset-grid">
            <div><span>درصد برد</span><b>{a['win_rate']:.1f}%</b></div>
            <div><span>تعداد معامله</span><b>{a['trades']}</b></div>
            <div><span>قدرت سود</span><b>{_pf(a['pf'])}</b></div>
            <div><span>بیشترین افت</span><b>{a['mdd']:.2f}%</b></div>
          </div>
          <div class="asset-foot">اگر با ۱۰٬۰۰۰ شروع می‌کردیم → {a['equity']:,.2f}</div>
        </article>
        """

    headline_pnl = f"{btc['pnl']:+,.0f}" if btc else "—"
    headline_wr = f"{btc['win_rate']:.0f}%" if btc else "—"
    headline_pf = _pf(btc["pf"]) if btc else "—"
    btc_equity = f"{btc['equity']:,.0f}" if btc else "—"

    html = f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>TR Bot — معرفی پروژه فاز ۱</title>
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
      line-height: 1.85;
    }}
    body::before {{
      content: "";
      position: fixed;
      inset: 0;
      pointer-events: none;
      opacity: 0.07;
      background-image:
        linear-gradient(rgba(182, 242, 109, 0.35) 1px, transparent 1px),
        linear-gradient(90deg, rgba(182, 242, 109, 0.35) 1px, transparent 1px);
      background-size: 48px 48px;
      mask-image: radial-gradient(circle at 50% 15%, black, transparent 75%);
    }}
    .wrap {{ position: relative; max-width: 980px; margin: 0 auto; padding: 28px 18px 80px; }}
    .mono {{ font-family: "IBM Plex Mono", monospace; direction: ltr; unicode-bidi: plaintext; }}
    .brand-row {{
      display: flex; justify-content: space-between; align-items: center; gap: 12px;
      margin-bottom: 22px; animation: rise 0.7s ease both;
    }}
    .logo {{ display: flex; align-items: center; gap: 12px; }}
    .mark {{
      width: 42px; height: 42px; border-radius: 12px;
      background: linear-gradient(145deg, var(--lime), #5cb86a);
      box-shadow: 0 0 0 1px rgba(182, 242, 109, 0.35), 0 10px 30px rgba(182, 242, 109, 0.25);
      position: relative;
    }}
    .mark::after {{
      content: ""; position: absolute; inset: 11px 9px;
      border-right: 3px solid #0a160f; border-bottom: 3px solid #0a160f; transform: skewX(-18deg);
    }}
    .logo strong {{ display: block; font-size: 1.05rem; }}
    .logo span {{ color: var(--muted); font-size: 0.82rem; }}
    .live-chip {{
      display: inline-flex; align-items: center; gap: 8px; padding: 8px 12px;
      border-radius: 999px; border: 1px solid var(--line); background: rgba(8, 20, 14, 0.7);
      color: var(--mint); font-size: 0.82rem;
    }}
    .live-chip i {{
      width: 8px; height: 8px; border-radius: 50%; background: var(--mint);
      box-shadow: 0 0 0 0 rgba(95, 224, 168, 0.7); animation: pulse 1.8s infinite;
    }}
    .hero {{
      position: relative; overflow: hidden; border: 1px solid var(--line); border-radius: 28px;
      padding: clamp(24px, 4vw, 40px);
      background:
        linear-gradient(135deg, rgba(16, 36, 28, 0.92), rgba(8, 18, 14, 0.88)),
        radial-gradient(600px 280px at 100% 0%, rgba(182, 242, 109, 0.18), transparent 60%);
      box-shadow: var(--shadow); animation: rise 0.8s ease both; margin-bottom: 18px;
    }}
    .hero::after {{
      content: ""; position: absolute; width: 280px; height: 280px; right: -60px; bottom: -90px;
      border-radius: 50%; background: radial-gradient(circle, rgba(182, 242, 109, 0.22), transparent 70%);
      filter: blur(8px); animation: drift 8s ease-in-out infinite alternate;
    }}
    .kicker {{ color: var(--lime); font-size: 0.92rem; font-weight: 600; margin-bottom: 10px; }}
    h1 {{
      margin: 0; font-size: clamp(2rem, 5vw, 3.1rem); line-height: 1.2; font-weight: 800;
      letter-spacing: -0.02em; max-width: 16ch;
    }}
    .hero-copy {{ margin: 14px 0 0; color: var(--muted); max-width: 40rem; font-size: 1.05rem; position: relative; z-index: 1; }}
    .hero-stats {{
      display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px;
      margin-top: 28px; position: relative; z-index: 1;
    }}
    .stat {{
      padding: 16px; border-radius: 18px; background: rgba(4, 12, 9, 0.55);
      border: 1px solid var(--line); backdrop-filter: blur(8px);
    }}
    .stat span {{ display: block; color: var(--muted); font-size: 0.82rem; margin-bottom: 6px; }}
    .stat b {{
      font-family: "IBM Plex Mono", monospace; font-size: clamp(1.25rem, 3vw, 1.7rem);
      font-weight: 600; direction: ltr; unicode-bidi: plaintext;
    }}
    .toc {{
      display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 8px; animation: rise 0.8s ease both;
    }}
    .toc a {{
      text-decoration: none; color: var(--text); font-size: 0.86rem; padding: 8px 12px;
      border-radius: 999px; border: 1px solid var(--line); background: rgba(8, 18, 14, 0.65);
    }}
    .section {{ margin-top: 26px; animation: rise 0.8s ease both; }}
    .section h2 {{ margin: 0 0 10px; font-size: 1.35rem; font-weight: 750; }}
    .section-note {{ color: var(--muted); margin: 0 0 14px; font-size: 0.95rem; }}
    .panel {{
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
      padding: 20px 18px; backdrop-filter: blur(10px);
    }}
    .panel p {{ margin: 0 0 12px; color: var(--muted); }}
    .panel p:last-child {{ margin-bottom: 0; }}
    .panel strong {{ color: var(--text); font-weight: 700; }}
    .steps {{
      display: grid; gap: 12px;
    }}
    .step {{
      display: grid; grid-template-columns: 52px 1fr; gap: 12px; align-items: start;
      background: rgba(0,0,0,0.18); border: 1px solid var(--line); border-radius: 16px; padding: 14px;
    }}
    .step-no {{
      width: 42px; height: 42px; border-radius: 12px; display: grid; place-items: center;
      background: rgba(182, 242, 109, 0.12); color: var(--lime); font-weight: 800;
    }}
    .step h3 {{ margin: 0 0 4px; font-size: 1.02rem; }}
    .step p {{ margin: 0; color: var(--muted); font-size: 0.95rem; }}
    .assets {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; }}
    .asset-card {{
      background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius);
      padding: 18px; backdrop-filter: blur(10px); animation: rise 0.8s ease both;
      transition: transform 0.25s ease, border-color 0.25s ease;
    }}
    .asset-card:hover {{ transform: translateY(-3px); border-color: rgba(182, 242, 109, 0.35); }}
    .asset-card.featured {{
      background: linear-gradient(180deg, rgba(182, 242, 109, 0.10), transparent 40%), var(--panel-solid);
      border-color: rgba(182, 242, 109, 0.35);
    }}
    .asset-top {{ display: flex; justify-content: space-between; gap: 10px; }}
    .asset-name {{ font-size: 1.2rem; font-weight: 700; }}
    .asset-name span {{ color: var(--muted); font-weight: 500; font-size: 0.9rem; }}
    .asset-range {{ color: var(--muted); font-size: 0.8rem; margin-top: 2px; }}
    .asset-badge {{
      height: fit-content; padding: 4px 10px; border-radius: 999px;
      background: rgba(182, 242, 109, 0.12); color: var(--lime); font-size: 0.78rem; font-weight: 600;
    }}
    .asset-pnl {{
      margin: 16px 0 12px; font-family: "IBM Plex Mono", monospace; font-size: 1.55rem;
      font-weight: 600; direction: ltr; unicode-bidi: plaintext;
    }}
    .up {{ color: var(--up); }}
    .down {{ color: var(--down); }}
    .asset-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; }}
    .asset-grid div {{ background: rgba(0,0,0,0.22); border-radius: 12px; padding: 10px 8px; text-align: center; }}
    .asset-grid span {{ display: block; color: var(--muted); font-size: 0.72rem; }}
    .asset-grid b {{ font-size: 0.95rem; }}
    .asset-foot {{ margin-top: 12px; color: var(--muted); font-size: 0.82rem; }}
    .glossary {{
      display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 10px;
    }}
    .term {{
      background: rgba(0,0,0,0.18); border: 1px solid var(--line); border-radius: 16px; padding: 14px;
    }}
    .term h3 {{ margin: 0 0 6px; font-size: 0.98rem; color: var(--lime); }}
    .term p {{ margin: 0; color: var(--muted); font-size: 0.9rem; }}
    .roadmap {{
      display: grid; gap: 10px;
    }}
    .road {{
      display: grid; grid-template-columns: 110px 1fr; gap: 12px; align-items: center;
      background: rgba(0,0,0,0.18); border: 1px solid var(--line); border-radius: 16px; padding: 14px;
    }}
    .road .tag {{
      text-align: center; border-radius: 999px; padding: 6px 10px; font-size: 0.8rem; font-weight: 700;
    }}
    .done {{ background: rgba(125, 255, 179, 0.12); color: var(--up); }}
    .now {{ background: rgba(182, 242, 109, 0.14); color: var(--lime); }}
    .next {{ background: rgba(142, 170, 154, 0.14); color: var(--muted); }}
    .road p {{ margin: 0; color: var(--muted); }}
    .road strong {{ color: var(--text); }}
    table {{ width: 100%; border-collapse: collapse; min-width: 560px; }}
    th, td {{ padding: 12px 10px; border-bottom: 1px solid var(--line); text-align: right; font-size: 0.92rem; }}
    th {{ color: var(--muted); font-weight: 600; font-size: 0.8rem; }}
    tr:last-child td {{ border-bottom: 0; }}
    .scroll {{ overflow: auto; }}
    .callout {{
      margin-top: 12px; padding: 14px 16px; border-radius: 16px;
      background: rgba(182, 242, 109, 0.08); border: 1px solid rgba(182, 242, 109, 0.22);
      color: var(--text);
    }}
    .footer {{ margin-top: 30px; color: var(--muted); font-size: 0.85rem; text-align: center; }}
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
      .hero-stats {{ grid-template-columns: 1fr; }}
      .road {{ grid-template-columns: 1fr; }}
      h1 {{ max-width: none; }}
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
          <span>معرفی ساده پروژه · فاز ۱</span>
        </div>
      </div>
      <div class="live-chip"><i></i> نسخهٔ آزمایشی</div>
    </div>

    <header class="hero">
      <div class="kicker">برای کسی که ترید یا برنامه‌نویسی بلد نیست</div>
      <h1>TR BOT چیست؟</h1>
      <p class="hero-copy">
        این پروژه، نسخهٔ اول یک <strong style="color:var(--text)">دستیار معاملاتی قانون‌محور</strong> است.
        یعنی به‌جای تصمیم احساسی، مجموعه‌ای از قانون‌های مشخص را روی داده‌های گذشته بازار کریپتو تست می‌کند
        تا ببینیم آیا این منطق اصلاً ارزش ادامه دارد یا نه.
      </p>
      <div class="hero-stats">
        <div class="stat"><span>نتیجه آزمایش روی بیت‌کوین</span><b class="{_pnl_class(btc['pnl']) if btc else ''}">{headline_pnl} USDT</b></div>
        <div class="stat"><span>چند درصد معامله‌ها سود شد</span><b>{headline_wr}</b></div>
        <div class="stat"><span>قدرت سود نسبت به ضرر</span><b>{headline_pf}</b></div>
      </div>
    </header>

    <nav class="toc" aria-label="فهرست">
      <a href="#why">هدف چیست؟</a>
      <a href="#how">چطور کار می‌کند؟</a>
      <a href="#done">چی پیاده شده؟</a>
      <a href="#results">نتایج یعنی چه؟</a>
      <a href="#words">کلمات سخت</a>
      <a href="#next">قدم بعدی</a>
    </nav>

    <section class="section" id="why">
      <h2>۱) هدف این پروژه چیست؟</h2>
      <div class="panel">
        <p>
          هدف نهایی این است که یک سیستم معاملاتی بسازیم که <strong>با قانون مشخص</strong> کار کند؛
          نه با حس و حال لحظه‌ای. اول روی داده‌های گذشته امتحان می‌شود، بعد اگر نتیجه پایدار بود،
          کم‌کم به حالت نیمه‌خودکار و در آینده شاید معامله واقعی می‌رسد.
        </p>
        <p>
          الان در <strong>فاز ۱</strong> هستیم: فقط تحقیق و آزمایش. هنوز پول واقعی وارد بازار نشده و
          ربات سفارش واقعی به صرافی نمی‌فرستد.
        </p>
        <div class="callout">
          فکر کن مثل ساختن یک ماشین است: اول موتور را روی میز تست می‌کنیم، بعد جاده آزمایشی،
          و آخر سر اگر ایمن بود می‌رود خیابان. ما الان مرحلهٔ تست روی میز هستیم.
        </div>
      </div>
    </section>

    <section class="section" id="how">
      <h2>۲) ایدهٔ معاملاتی به زبان خیلی ساده</h2>
      <p class="section-note">ربات دنبال یک سناریوی تکراری در چارت می‌گردد:</p>
      <div class="steps">
        <div class="step">
          <div class="step-no">۱</div>
          <div>
            <h3>شکار نقدینگی (Liquidity Sweep)</h3>
            <p>قیمت برای لحظه‌ای از یک سقف یا کف مهم رد می‌شود تا سفارش‌های پشت آن را فعال کند، بعد برمی‌گردد.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۲</div>
          <div>
            <h3>تغییر ساختار (MSS)</h3>
            <p>بعد از آن برگشت، اگر قیمت ساختار قبلی بازار را بشکند، سیستم می‌گوید «احتمالاً جهت عوض شده».</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۳</div>
          <div>
            <h3>ورود با ریسک کنترل‌شده</h3>
            <p>اگر وارد شود، حد ضرر پشت همان نقطهٔ شکار نقدینگی است و هدف سود حدود ۲ برابر ریسک است. در هر معامله فقط ۱٪ کل سرمایه ریسک می‌شود.</p>
          </div>
        </div>
        <div class="step">
          <div class="step-no">۴</div>
          <div>
            <h3>فیلتر کیفیت</h3>
            <p>فقط وقتی وارد می‌شود که جهت کلی روزانه هم‌سو باشد و ساعت بازار در بازهٔ لندن/نیویورک باشد. اگر روز بدی باشد یا چند ضرر پشت‌سرهم بخورد، موقتاً دست نگه می‌دارد.</p>
          </div>
        </div>
      </div>
    </section>

    <section class="section" id="done">
      <h2>۳) تا اینجا چه چیزهایی ساخته شده؟</h2>
      <div class="panel">
        <p><strong>موتور استراتژی:</strong> تشخیص سقف/کف، شکار نقدینگی، تغییر ساختار، و صدور سیگنال.</p>
        <p><strong>موتور بک‌تست:</strong> روی تاریخچهٔ قیمت، معامله‌ها را شبیه‌سازی می‌کند و سود/ضرر را حساب می‌کند.</p>
        <p><strong>مدیریت ریسک:</strong> سقف ضرر روزانه، توقف بعد از چند ضرر متوالی، و درنظرگرفتن کارمزد/اسلیپیج.</p>
        <p><strong>اعتبارسنجی:</strong> تست روی بیت‌کوین، اتریوم، سولانا + تست تکه‌تکه روی بازه‌های زمانی مختلف.</p>
        <p><strong>حالت Paper:</strong> می‌تواند از اینترنت قیمت بگیرد و فقط سیگنال بدهد؛ بدون ثبت سفارش واقعی.</p>
        <p><strong>این صفحه:</strong> گزارش قابل‌اشتراک برای توضیح پروژه به افراد غیرتخصصی.</p>
      </div>
    </section>

    <section class="section" id="results">
      <h2>۴) نتایج آزمایش یعنی چه؟</h2>
      <p class="section-note">
        فرض آزمایش: شروع با ۱۰٬۰۰۰ تتر، تایم‌فریم ۴ ساعته، با احتساب هزینه معامله.
        عدد سبز یعنی در آن آزمایش سودآور بوده؛ قرمز یعنی زیان.
      </p>
      <div class="assets">{asset_cards}</div>

      <div class="panel" style="margin-top:16px">
        <p>
          روی <strong>بیت‌کوین</strong> نتیجه فعلاً امیدوارکننده‌تر است
          (حدود {headline_pnl} سود آزمایشی و سرمایه نهایی حدود {btc_equity}).
          روی اتریوم هنوز ضعیف است. یعنی این منطق فعلاً «برای همه ارزها عالی» نیست و باید محتاط باشیم.
        </p>
      </div>

      <h2 style="margin-top:22px">تست تکه‌تکه روی بیت‌کوین (Walk-Forward)</h2>
      <p class="section-note">
        یعنی داده‌ها را تکه‌تکه کرده‌ایم (هر تکه حدود ۹۰ روز) تا ببینیم نتیجه فقط شانس یک بازه خاص نبوده.
        فعلاً {positive_folds} از {total_folds} تکه مثبت شده؛ خوب است ولی هنوز یکنواخت کامل نیست.
      </p>
      <div class="panel scroll">
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

    <section class="section" id="words">
      <h2>۵) واژه‌هایی که ممکن است سخت به نظر برسند</h2>
      <div class="glossary">
        <div class="term"><h3>بک‌تست</h3><p>امتحان استراتژی روی قیمت‌های گذشته، مثل بازپخش فیلم بازی‌های قبلی.</p></div>
        <div class="term"><h3>سیگنال</h3><p>پیامی که می‌گوید الان شرایط ورود به معامله از نظر قوانین سیستم برقرار است.</p></div>
        <div class="term"><h3>حد ضرر (SL)</h3><p>خط قرمز خروج؛ اگر قیمت به آنجا برسد معامله بسته می‌شود تا ضرر بزرگ نشود.</p></div>
        <div class="term"><h3>حد سود (TP)</h3><p>هدف قیمتی برای بستن معامله با سود.</p></div>
        <div class="term"><h3>Win Rate</h3><p>از هر ۱۰۰ معامله، چندتایش سود بوده.</p></div>
        <div class="term"><h3>Max Drawdown</h3><p>بیشترین افت سرمایه از قله تا دره در طول آزمایش.</p></div>
        <div class="term"><h3>Profit Factor</h3><p>جمع سودها تقسیم بر جمع ضررها. بالاتر از ۱ یعنی سود کل بیشتر از ضرر کل بوده.</p></div>
        <div class="term"><h3>Paper Trading</h3><p>تمرین با سیگنال واقعی بازار، بدون گذاشتن پول واقعی.</p></div>
      </div>
    </section>

    <section class="section" id="next">
      <h2>۶) قرار است به کدام سمت برود؟</h2>
      <div class="roadmap">
        <div class="road">
          <div class="tag done">انجام شده</div>
          <p><strong>فاز ۱:</strong> ساخت هسته قوانین + بک‌تست + ریسک + گزارش اشتراک</p>
        </div>
        <div class="road">
          <div class="tag now">الان اینجا هستیم</div>
          <p><strong>مانیتور Paper:</strong> چند روز سیگنال‌ها را بدون پول واقعی نگاه می‌کنیم و با چشم انسان چک می‌کنیم</p>
        </div>
        <div class="road">
          <div class="tag next">بعدی</div>
          <p><strong>Demo/Testnet:</strong> اگر سیگنال‌ها تمیز بودند، سفارش آزمایشی روی حساب تست</p>
        </div>
        <div class="road">
          <div class="tag next">آینده</div>
          <p><strong>نسخه جدی‌تر:</strong> داشبورد، هشدار، اتصال امن به صرافی، و فقط در صورت پایداری آمار</p>
        </div>
      </div>
      <div class="callout" style="margin-top:14px">
        مهم: این صفحه تضمین سود نیست. فقط نشان می‌دهد تیم چه چیزی ساخته، چرا ساخته،
        و فعلاً در آزمایش اولیه به چه نتیجه‌ای رسیده است.
      </div>
    </section>

    <div class="footer">
      TR BOT · Phase 1 Report · بدون معامله واقعی · ساخته‌شده برای توضیح شفاف به افراد غیرتخصصی
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
    (Path("docs") / ".nojekyll").write_text("", encoding="utf-8")
    print(f"Wrote beginner report -> {out_share.resolve()}")
    print(f"Wrote GitHub Pages report -> {out_docs.resolve()}")


if __name__ == "__main__":
    main()
