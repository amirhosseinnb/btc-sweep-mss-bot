# AJV — ساختار کامل سیستم (۱۷ بخش)

**Amir · Javid · Vahid** · فاز ۱ تحقیقاتی / Paper فقط‌خواندنی

این سند نگاشت «ساختار پیشنهادی» به کد واقعی مخزن است.  
ساعت پروژه: `America/New_York` · تمرکز پیش‌فرض: `BTCUSDT` تایم‌فریم `4h`.

---

## ۱) Trading Philosophy

**وضعیت:** پیاده + سند  
**کد:** `philosophy.py`  
**اصول:** قانون‌محور، ریسک ≤ ۱٪، حداقل R:R = ۲، بدون سفارش واقعی در فاز ۱، احترام به No-Trade.  
**اجرا:** `check_philosophy(strategy, backtest)` در `run.py` گزارش می‌دهد.

جزئیات بیشتر: [`PHILOSOPHY.md`](./PHILOSOPHY.md)

---

## ۲) Price Action Framework

**وضعیت:** پیاده  
**کد:** `price_action.py`  
**محتوا:**
- Swing points (از `core_strategy.detect_swing_points`)
- `BOS` / `CHOCH` از روی شکست سقف/کف سوئینگ
- Impulse / Retracement بین سوئینگ‌ها
- Dealing Range فعال برای Premium/Discount

**فیلتر اختیاری:** `--require-choch`

---

## ۳) ICT Framework

**وضعیت:** پیاده  
**کد:** `ict.py`  
**محتوا:**
- Fair Value Gap (FVG)
- Order Block (آخرین کندل مخالف قبل از MSS)
- Premium / Discount نسبت به dealing range
- OTE (۶۱٫۸٪–۷۹٪ از ایمپالس Sweep→MSS)

**فیلترها:** `--require-order-block` · `--require-pd-alignment` · `--require-ote`  
**ورود FVG:** `--entry-mode fvg_retrace` یا preset `best_fvg`

---

## ۴) Market Structure

**وضعیت:** پیاده  
**کد:** `core_strategy.py`  
MSS گاوی/خرسی پس از Sweep: کلوز بالای/زیر swing مخالف.

---

## ۵) Liquidity & Sweep

**وضعیت:** پیاده  
**کد:** `core_strategy.py` (`detect_liquidity_sweeps`)  
فیلتر نفوذ مینیمم: `--min-sweep-atr`

---

## ۶) CRT — Candle Range Theory

**وضعیت:** پیاده  
**کد:** `crt.py`  
- رنج روز قبل NY  
- `--require-crt-sweep` · `--require-crt-reclaim`  
در preset `full` مقدار reclaim روشن است.

---

## ۷) Divergence

**وضعیت:** پیاده  
**کد:** `divergence.py`  
`--require-divergence` · در preset `full` روشن است.

---

## ۸) Confluence & Setup Formation

**وضعیت:** پیاده  
**کد:** `scoring.py` + فیلترهای کیفیت در `generate_signals`  
زنجیره: Sweep → (Reclaim) → MSS → فیلترها → Score → Entry

---

## ۹) Long Setup Rules / ۱۰) Short Setup Rules

**وضعیت:** پیاده  
**کد:** `core_strategy.py`  
Long: bullish sweep + MSS بالا · Short: bearish sweep + MSS پایین

---

## ۱۱) Entry Rules

**وضعیت:** پیاده  
`--entry-mode`: `mss_close` | `first_retracement` | `fvg_retrace`

---

## ۱۲) Stop Loss & Take Profit

**وضعیت:** پیاده  
SL پشت `sweep_extreme` · TP با R:R ≥ ۲ (`StrategyConfig.risk_reward`)

---

## ۱۳) Risk Management

**وضعیت:** پیاده  
**کد:** `risk.py` + سایز در `backtester.py`  
- ۱٪ ریسک در هر معامله  
- حد ضرر روزانه (پیش‌فرض ۳٪)  
- قفل بعد از N ضرر متوالی (پیش‌فرض ۳)

---

## ۱۴) 24-Point Scoring System

**وضعیت:** پیاده  
**کد:** `scoring.py`  

| بخش | سقف |
|---|---|
| Sweep | ۴ |
| Structure / MSS (+CHOCH) | ۴ |
| HTF Bias | ۳ |
| Session | ۳ |
| CRT | ۳ |
| Divergence | ۳ |
| ICT Zone (FVG/OB/OTE/PD) | ۲ |
| Timing | ۲ |
| **جمع** | **۲۴** |

`--enable-scoring --min-score N`

---

## ۱۵) No-Trade Conditions

**وضعیت:** پیاده  
**کد:** `no_trade.py`  
- قفل ریسک (ضرر روزانه / ضرر متوالی)  
- سقف معامله در روز: `--max-trades-per-day`  
- کول‌داون بعد از ضرر: `--cooldown-bars-after-loss`  
به‌علاوه فیلترهای استراتژی (session/HTF/CRT/div/score/ICT)

---

## ۱۶) Trade Management

**وضعیت:** پیاده  
**کد:** `trade_management.py`  
`--manage-trades` · Breakeven · Partial · Trailing  
ترتیب محافظه‌کارانه: اول خروج با استاپ قبلی، بعد به‌روزرسانی مدیریت.

---

## ۱۷) Backtesting Protocol

**وضعیت:** پیاده  
**کد:** `backtester.py` · `run.py` · `validate.py`  
کارمزد/اسلیپیج/اسپرد · Walk-Forward و چندنماد در `validate.py`

---

## Presetها

| Preset | معنی |
|---|---|
| `best` | HTF + session (baseline پایدار فاز ۱) |
| `best_fvg` | همان + ورود FVG |
| `full` | HTF + session + CRT reclaim + divergence + scoring(≥۱۴) + trade manage |

```bash
python run.py --csv data/btcusdt_4h.csv --preset best
python run.py --csv data/btcusdt_4h.csv --preset full
python validate.py
```

---

## فایل‌های کلیدی

| نقش | مسیر |
|---|---|
| فلسفه | `philosophy.py` · `docs/PHILOSOPHY.md` |
| Price Action | `price_action.py` |
| ICT | `ict.py` |
| CRT | `crt.py` |
| Divergence | `divergence.py` |
| استراتژی | `core_strategy.py` |
| امتیاز | `scoring.py` |
| No-Trade | `no_trade.py` |
| مدیریت معامله | `trade_management.py` |
| ریسک | `risk.py` |
| بک‌تست | `backtester.py` · `run.py` · `validate.py` |
| Paper | `paper_trader.py` |
| دموی وب | `docs/index.html` · `share/index.html` |

---

## نکته مهم

این ساختار برای تحقیق و Paper است.  
**تضمین سود نیست** و تا تأیید پایدار نتایج، سفارش واقعی ارسال نمی‌شود.
