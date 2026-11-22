# AJV Rulebook (executable)

منبع: اسناد Rulebook و منابع معاملاتی پروژه.  
این سند نگاشت قوانین به کد فعلی است.

## فلسفه

معامله فقط با قانون. اول بقا، بعد سود. بدون confluence کافی → No Trade.  
فاز ۱: بدون سفارش واقعی.

## زنجیرهٔ ایده‌آل

HTF Bias → Market Structure → Key Zone / PD → CRT Range → Liquidity Sweep → Divergence → Reclaim → Displacement → MSS/BOS → FVG/OB → Entry → SL → TP / Liquidity Target

## قانون طلایی

Sweep به‌تنهایی ورود نیست.

- **LONG** = Sweep Low + Reclaim + Bullish Displacement + MSS + Retracement  
- **SHORT** = Sweep High + Reclaim + Bearish Displacement + MSS + Retracement  
- حداقل بحرانی همیشه: **Sweep + MSS + R:R ≥ ۱:۲**

## امتیاز ۲۴تایی (۱۲ × ۰–۲)

| فاکتور | سقف | کد |
|---|---|---|
| HTF Bias | ۰–۲ | `scoring.py` |
| Market Structure | ۰–۲ | CHOCH / BOS / HTF |
| Key Zone | ۰–۲ | PD / OTE |
| CRT Range | ۰–۲ | sweep + reclaim |
| Liquidity Sweep | ۰–۲ | نفوذ ATR |
| Divergence | ۰–۲ | Regular=۲ / Hidden=۱ |
| Reclaim | ۰–۲ | CRT reclaim |
| Displacement | ۰–۲ | بدنه نسبت به ATR |
| MSS/BOS | ۰–۲ | تأیید شکست |
| FVG / OB | ۰–۲ | ناحیه ورود |
| Liquidity Target | ۰–۲ | هدف نقدینگی |
| Risk-to-Reward | ۰–۲ | ≥۲ و ≥۲.۵ |

### باند تصمیم

| امتیاز | کیفیت |
|---|---|
| ۰–۱۱ | No Trade |
| ۱۲–۱۵ | Weak |
| ۱۶–۱۸ | Review |
| ۱۹–۲۱ | Good |
| ۲۲–۲۴ | A+ |

Preset `javid`: `min_score=16` + `reject_weak_scores` + فیلترهای CRT sweep/reclaim + Displacement + Divergence + `risk_reward=2.5` + `tp_mode=liquidity` + سقف ۱ معامله/روز و کول‌داون ۲ بار.  
PD و FVG به‌صورت امتیاز Key Zone / FVG-OB ترجیح داده می‌شوند (نه همیشه hard-reject، تا نمونهٔ بک‌تست صفر نشود).

## No-Trade

علاوه بر فیلترهای استراتژی: سقف معامله روزانه، کول‌داون بعد از ضرر، حد ضرر روزانه، قفل ضرر متوالی — `no_trade.py` / `risk.py`.

## مسیر اجرا

```bash
python run.py --csv data/btcusdt_4h.csv --preset javid
python run.py --csv data/btcusdt_4h.csv --preset full
python validate.py
```

## وضعیت فاز ۱

پوشش اجرایی قوانین، بک‌تست، Walk-Forward، Paper فقط‌خواندنی، و گزارش UI کامل است.

## خارج از فاز ۱ (عمدی)

FastAPI / Next.js / PostgreSQL / سفارش واقعی صرافی — مسیر بعدی فقط بعد از پایداری Paper: Demo/Testnet → Live.
