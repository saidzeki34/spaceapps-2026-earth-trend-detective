"""Turning numbers into short, plain text for the screens."""

from __future__ import annotations

import math

MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
MINUS = "−"  # a real minus sign


def is_number(value) -> bool:
    return isinstance(value, (int, float)) and math.isfinite(value)


def number(value, unit: str = "") -> str:
    """About three meaningful digits, e.g. 1,234 / 56.7 / 2.34 / 0.123."""
    if not is_number(value):
        return "—"
    size = abs(value)
    if size >= 100:
        text = f"{value:,.0f}"
    elif size >= 10:
        text = f"{value:.1f}"
    elif size >= 1:
        text = f"{value:.2f}"
    else:
        text = f"{value:.3f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")  # 2.50 -> 2.5, 2.00 -> 2
    if float(text.replace(",", "")) == 0:
        text = text.lstrip("-")
    text = text.replace("-", MINUS)
    return f"{text} {unit}".strip()


def signed(value, unit: str = "") -> str:
    text = number(value, unit)
    return text if text.startswith(MINUS) or not is_number(value) or value == 0 else "+" + text


def p_value(p) -> str:
    if not is_number(p):
        return "p not available"
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}" if p < 0.01 else f"p = {p:.2f}"


def month_list(months: list[int]) -> str:
    """[12, 1, 2] -> 'Dec, Jan and Feb' (months are numbered 1-12)."""
    names = [MONTHS[m - 1] for m in months]
    if len(names) <= 1:
        return "".join(names)
    return ", ".join(names[:-1]) + " and " + names[-1]


def plural(count: int, word: str) -> str:
    return f"{count} {word}" if count == 1 else f"{count} {word}s"


def clean(value):
    """Make a result safe to send as JSON: plain Python types, and None instead of NaN."""
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [clean(v) for v in value]
    if hasattr(value, "item") and not isinstance(value, (str, bytes)):
        try:
            value = value.item()  # numpy scalar -> Python scalar
        except (ValueError, AttributeError):
            return [clean(v) for v in value.tolist()]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value
