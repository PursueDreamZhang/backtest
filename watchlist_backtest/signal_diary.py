from __future__ import annotations

import os
from concurrent.futures import ProcessPoolExecutor
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict

import pandas as pd

from research.data_loader import load_symbol_frames
from watchlist.config import WatchlistConfig, load_watchlist_config
from watchlist.indicators import enrich_daily_indicators
from watchlist.signals import evaluate_symbol

SIGNAL_LOOKBACK_ROWS = 140
DEFAULT_MAX_WORKERS = max(1, min(8, (os.cpu_count() or 2) - 1))

FIVE_PERCENT_TRIGGER_SETUPS = {
    "MA40 弹簧压紧后松开",
    "整理后第一根启动阳线",
    "双底或二次压紧",
}


def load_watchlist_frames(
    config_path: str,
    start_date: str,
    end_date: str,
):
    loaded = load_watchlist_config(config_path)
    configs = loaded if isinstance(loaded, list) else [loaded]
    symbol_meta: dict[str, dict] = {}
    direction_by_symbol: dict[str, set[str]] = {}
    for config in configs:
        assert isinstance(config, WatchlistConfig)
        for item in config.symbols:
            symbol_meta.setdefault(
                item.symbol,
                {
                    "symbol": item.symbol,
                    "name": item.name,
                    "instrument_type": item.instrument_type,
                },
            )
            direction_by_symbol.setdefault(item.symbol, set()).add(config.direction)

    frames = load_symbol_frames(sorted(symbol_meta.keys()), start_date, end_date)
    return configs, symbol_meta, direction_by_symbol, frames


def compute_trigger_price(signal_row: dict, frame: pd.DataFrame) -> tuple[float | None, str | None]:
    if signal_row.get("group") != "触发买点" or frame.empty:
        return None, None

    setup = signal_row.get("setup")
    latest_row = frame.iloc[-1]
    if setup in FIVE_PERCENT_TRIGGER_SETUPS:
        latest_price = signal_row.get("latest_price", latest_row.get("close"))
        if latest_price is None or pd.isna(latest_price):
            return None, None
        return round(float(latest_price) * 1.05, 6), "prev_close_x_1.05"

    if setup == "MA20 第一次回档":
        ma20 = latest_row.get("ma20")
        if ma20 is None or pd.isna(ma20):
            return None, None
        return round(float(ma20), 6), "signal_day_ma20"

    return None, None


def _build_symbol_rows(task: tuple[str, dict, list[dict], pd.DataFrame, str, str]) -> list[dict]:
    symbol, base, contexts, frame, start_date, end_date = task
    full_frame = enrich_daily_indicators(frame.sort_index())
    rows: list[dict] = []
    start_index = 59 if len(full_frame) >= 60 else len(full_frame)
    for idx in range(start_index, len(full_frame)):
        trade_dt = full_frame.index[idx]
        trade_date = trade_dt.strftime("%Y%m%d")
        if trade_date < start_date or trade_date > end_date:
            continue
        window_start = max(0, idx - SIGNAL_LOOKBACK_ROWS + 1)
        sliced = full_frame.iloc[window_start : idx + 1]
        result = evaluate_symbol(
            symbol=symbol,
            name=base["name"],
            instrument_type=base["instrument_type"],
            frame=sliced,
            mode="close_confirmed",
            expected_end_date=trade_date,
        )
        base_row = asdict(result)
        base_row["trade_date"] = trade_date
        trigger_price, trigger_price_rule = compute_trigger_price(base_row, sliced)
        base_row["trigger_price"] = trigger_price
        base_row["trigger_price_rule"] = trigger_price_rule
        for context in contexts:
            row = dict(base_row)
            row["direction"] = context["direction"]
            row["thesis"] = context["thesis"]
            rows.append(row)
    return rows


def build_signal_diary(
    config_path: str,
    start_date: str,
    end_date: str,
    *,
    max_workers: int | None = None,
) -> tuple[pd.DataFrame, dict[str, pd.DataFrame]]:
    configs, symbol_meta, _, frames = load_watchlist_frames(config_path, start_date, end_date)
    rows: list[dict] = []
    symbol_contexts: dict[str, list[dict]] = {}

    for config in configs:
        for item in config.symbols:
            symbol_contexts.setdefault(item.symbol, []).append(
                {
                    "direction": config.direction,
                    "thesis": config.thesis,
                }
            )

    tasks = [
        (symbol, symbol_meta[symbol], contexts, frames[symbol], start_date, end_date)
        for symbol, contexts in symbol_contexts.items()
    ]
    workers = max_workers if max_workers is not None else DEFAULT_MAX_WORKERS
    if workers <= 1 or len(tasks) <= 1:
        for task in tasks:
            rows.extend(_build_symbol_rows(task))
    else:
        try:
            with ProcessPoolExecutor(max_workers=workers) as executor:
                for symbol_rows in executor.map(_build_symbol_rows, tasks):
                    rows.extend(symbol_rows)
        except (PermissionError, OSError):
            with ThreadPoolExecutor(max_workers=workers) as executor:
                for symbol_rows in executor.map(_build_symbol_rows, tasks):
                    rows.extend(symbol_rows)

    diary = pd.DataFrame(rows)
    if not diary.empty:
        diary = diary.sort_values(["trade_date", "direction", "symbol"]).reset_index(drop=True)
    return diary, frames
