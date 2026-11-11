# فلسفهٔ معاملاتی AJV

**فاز:** Phase 1 — Research / Paper only  
**تیم:** Amir · Javid · Vahid

## اصول فارسی

1. معامله فقط با قانون؛ نه احساس و نه پیش‌بینی خبر.
2. اول بقا، بعد سود: ریسک هر معامله حداکثر ۱٪ و حداقل R:R برابر ۲.
3. بدون confluence کافی وارد نشو؛ سیگنال ضعیف را رد کن.
4. اگر شرایط No-Trade فعال است، هیچ ورود جدیدی مجاز نیست.
5. تا پایان فاز ۱ هیچ سفارش واقعی به صرافی ارسال نمی‌شود.
6. هر تغییر قانون باید با بک‌تست و Walk-Forward سنجیده شود.

## Principles (EN)

1. Rules over emotion: every entry must map to coded conditions.
2. Survival first: max 1% risk per trade and minimum 2R reward.
3. No weak setups: confluence/score gates beat FOMO.
4. No-Trade means no-trade — circuit breakers win.
5. Phase 1 is read-only / paper; live orders are forbidden.
6. Change the rules only after offline validation.

## Enforcement in code

| اصل | محل اعمال |
|---|---|
| R:R ≥ ۲ | `StrategyConfig.risk_reward` در `core_strategy.py` |
| ریسک ۱٪ | `BacktestConfig.risk_per_trade` در `backtester.py` |
| بدون سفارش واقعی | `paper_trader.py` / `live.json` → `orders_enabled=false` |
| No-Trade | `no_trade.py` + `risk.py` |
| Confluence | `scoring.py` + فیلترهای ICT/PA |
| صحت‌سنجی فلسفه | `philosophy.check_philosophy()` در `run.py` |

## تعریف عملی «آمادگی ورود»

یک ستاپ فقط وقتی معتبر است که:

1. Sweep و MSS قانون‌مند رخ داده باشد
2. فیلترهای اجباری preset پاس شده باشند
3. اگر scoring روشن است، امتیاز ≥ `min_score` باشد
4. Risk/No-Trade اجازهٔ ورود بدهد
5. اندازهٔ پوزیشن از فاصلهٔ SL و ۱٪ حساب به‌دست بیاید

اگر یکی از این‌ها برقرار نباشد: **No Trade**.
