"""Gregorian ↔ Jalali helpers (no external deps)."""

from __future__ import annotations

from datetime import date, datetime
from typing import Union


def gregorian_to_jalali(gy: int, gm: int, gd: int) -> tuple[int, int, int]:
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    gy2 = gy + 1 if gm > 2 else gy
    days = (
        355666
        + (365 * gy)
        + ((gy2 + 3) // 4)
        - ((gy2 + 99) // 100)
        + ((gy2 + 399) // 400)
        + gd
        + g_d_m[gm - 1]
    )
    jy = -1595 + (33 * (days // 12053))
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return int(jy), int(jm), int(jd)


def format_jalali(
    value: Union[str, date, datetime],
    *,
    with_time: bool = False,
) -> str:
    if isinstance(value, str):
        raw = value.replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError:
            # date-only
            d = date.fromisoformat(raw[:10])
            jy, jm, jd = gregorian_to_jalali(d.year, d.month, d.day)
            return f"{jy:04d}/{jm:02d}/{jd:02d}"
    elif isinstance(value, datetime):
        dt = value
    elif isinstance(value, date):
        jy, jm, jd = gregorian_to_jalali(value.year, value.month, value.day)
        return f"{jy:04d}/{jm:02d}/{jd:02d}"
    else:
        return "—"

    jy, jm, jd = gregorian_to_jalali(dt.year, dt.month, dt.day)
    base = f"{jy:04d}/{jm:02d}/{jd:02d}"
    if with_time:
        return f"{base} {dt.hour:02d}:{dt.minute:02d}"
    return base


def dual_date(
    value: Union[str, date, datetime],
    *,
    with_time: bool = False,
) -> dict[str, str]:
    if isinstance(value, str):
        g = value[:10]
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if with_time:
                g = dt.strftime("%Y-%m-%d %H:%M")
            else:
                g = dt.strftime("%Y-%m-%d")
        except ValueError:
            pass
    elif isinstance(value, datetime):
        g = value.strftime("%Y-%m-%d %H:%M") if with_time else value.strftime("%Y-%m-%d")
    else:
        g = value.isoformat()
    return {
        "gregorian": g,
        "jalali": format_jalali(value, with_time=with_time),
        "label": f"{g} · {format_jalali(value, with_time=with_time)}",
    }
