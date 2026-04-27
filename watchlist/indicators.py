from __future__ import annotations

import pandas as pd


def enrich_daily_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    work = frame.copy().sort_index()
    work["ma5"] = work["close"].rolling(5).mean()
    work["ma20"] = work["close"].rolling(20).mean()
    work["ma40"] = work["close"].rolling(40).mean()
    work["ma120"] = work["close"].rolling(120).mean()
    work["vol5"] = work["volume"].rolling(5).mean()
    work["vol20"] = work["volume"].rolling(20).mean()
    work["ret20"] = work["close"] / work["close"].shift(20) - 1.0
    work["ret40"] = work["close"] / work["close"].shift(40) - 1.0
    work["high20"] = work["high"].rolling(20).max()
    work["low20"] = work["low"].rolling(20).min()
    work["low60"] = work["low"].rolling(60).min()
    work["drawdown20"] = work["close"] / work["high"].rolling(20).max() - 1.0
    return work


def support_distance_pct(price: float, support: float | None) -> float | None:
    if support is None or support == 0:
        return None
    return (price / support - 1.0) * 100


def volume_progress(current_volume: float | None, avg_volume: float | None) -> float | None:
    if current_volume is None or avg_volume in (None, 0):
        return None
    return current_volume / avg_volume
