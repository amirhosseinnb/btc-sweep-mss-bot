# AJV — Phase 1 Research Demo

**Amir · Javid · Vahid**

سیستم معاملاتی قانون‌محور برای کریپتو (ICT/SMC) با بک‌تست، مدیریت ریسک، امتیاز confluence، و مانیتور زنده فقط‌خواندنی.

> دموی عمومی:  
> **https://amirhosseinnb.github.io/btc-sweep-mss-bot/**  
>
> صفحه آنلاین است، به بازار وصل می‌شود (فقط خواندنی)، و حدوداً **هر ۲ ساعت** آپدیت می‌شود.  
> هنوز سفارش واقعی ارسال نمی‌کند.

## هدف

به‌جای معامله احساسی، مجموعه‌ای از قانون‌های مشخص را روی داده‌های گذشته بازار تست می‌کنیم تا ببینیم آیا این منطق ارزش ادامه دارد یا نه.

الان در **فاز ۱** هستیم:

- هنوز سفارش واقعی به صرافی ارسال نمی‌شود
- هدف، ساخت و آزمایش هستهٔ قوانین است
- تمرکز فعلی روی بیت‌کوین تایم‌فریم ۴ ساعته است

## ساختار کامل (۱۷ بخش)

سند مرجع پیاده‌سازی:

- [`docs/AJV_STRUCTURE.md`](docs/AJV_STRUCTURE.md) — نگاشت کامل ساختار پیشنهادی به کد
- [`docs/PHILOSOPHY.md`](docs/PHILOSOPHY.md) — فلسفهٔ معاملاتی AJV

پوشش فعلی: Philosophy، Price Action (BOS/CHOCH)، ICT (FVG/OB/OTE/PD)، Market Structure، Sweep، CRT، Divergence، Confluence، Long/Short، Entry، SL/TP، Risk، 24-Point Score، No-Trade، Trade Management، Backtesting.

## منطق ورود

1. قیمت یک سقف/کف مهم را لحظه‌ای رد می‌کند (Liquidity Sweep)
2. بعد برمی‌گردد و ساختار بازار را می‌شکند (MSS / BOS-CHOCH)
3. فیلترها و (اختیاری) امتیاز ۲۴تایی بررسی می‌شوند
4. حد ضرر پشت نقطهٔ sweep است و هدف سود حداقل ۲ برابر ریسک است
5. در هر معامله فقط ۱٪ سرمایه ریسک می‌شود

## پیاده‌سازی فعلی

- موتور استراتژی Sweep / MSS + فیلترهای ICT/PA
- امتیاز confluence ۲۴تایی (`scoring.py`)
- No-Trade gate و Trade Management (BE / partial / trail)
- بک‌تست آفلاین با کارمزد + اسلیپیج + اسپرد
- مدیریت ریسک (ضرر روزانه / ضررهای متوالی)
- اعتبارسنجی چندنماد و Walk-Forward
- Paper Trader فقط‌خواندنی
- دموی عمومی AJV روی GitHub Pages

## مسیر بعدی

1. **الان:** مانیتور سیگنال‌های Paper بدون پول واقعی  
2. **بعد:** حساب Demo/Testnet اگر کیفیت سیگنال خوب بود  
3. **آینده:** داشبورد، هشدار، و اتصال امن‌تر به صرافی فقط در صورت پایداری نتایج

## اجرای محلی

```bash
pip install -r requirements.txt
python download_data.py --symbol BTCUSDT --timeframe 4h --days 730
python run.py --csv data/btcusdt_4h.csv --preset best
python run.py --csv data/btcusdt_4h.csv --preset full
python validate.py
python paper_trader.py --once
python make_share_report.py
```

### Presetها

| Preset | توضیح |
|---|---|
| `best` | HTF + session — baseline پایدار |
| `best_fvg` | همان + ورود از FVG |
| `full` | CRT reclaim + divergence + scoring + trade manage |

## نکته مهم

این مخزن و دموی آن **تضمین سود نیستند**.  
فقط وضعیت فاز ۱ پروژه و نتایج آزمایش اولیه را شفاف نشان می‌دهند.
