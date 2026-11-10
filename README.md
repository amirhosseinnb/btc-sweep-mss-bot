# TR Bot — Phase 1 (Rule-based Sweep / MSS)

آفلاین بک‌تست استراتژی ICT-lite روی کریپتو، با تمرکز روی **BTCUSDT 4H**.

## Quick start

```bash
pip install -r requirements.txt
python download_data.py --symbol BTCUSDT --timeframe 4h --days 730
python run.py --csv data/btcusdt_4h.csv --preset best
python validate.py
python paper_trader.py --once
```

## Share report

```bash
python make_share_report.py
```

سپس فایل `share/index.html` را برای دوستت بفرست یا در مرورگر باز کن.

## Preset `best`

- HTF daily bias
- London/NY session (America/New_York)
- Entry on MSS close
- Fee + slippage + spread
- Daily loss limit / consecutive-loss guards

## Notes

- هنوز سفارش واقعی ارسال نمی‌شود.
- Paper mode فقط سیگنال می‌سازد و لاگ می‌کند.
