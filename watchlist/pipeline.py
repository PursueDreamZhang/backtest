from __future__ import annotations

from datetime import datetime
import inspect
from typing import Callable

from data.realtime_quote_source import RealtimeQuoteSource
from research.data_loader import load_symbol_frames

from .config import WatchlistConfig, load_watchlist_config
from .reporting import write_reports
from .signals import evaluate_symbol


def run_watchlist_strategy(
    config_path: str,
    output_dir: str,
    start_date: str,
    end_date: str,
    *,
    mode: str = "close_confirmed",
    frame_loader: Callable | None = None,
    realtime_quote_loader: Callable | None = None,
    cache_only: bool = False,
) -> dict[str, str]:
    if mode not in {"intraday", "close_confirmed"}:
        raise ValueError("mode must be intraday or close_confirmed")

    loaded_config = load_watchlist_config(config_path)
    if isinstance(loaded_config, list):
        return _run_many(
            loaded_config,
            output_dir=output_dir,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            frame_loader=frame_loader,
            realtime_quote_loader=realtime_quote_loader,
            cache_only=cache_only,
        )
    return _run_one(
        loaded_config,
        output_dir=output_dir,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        frame_loader=frame_loader,
        realtime_quote_loader=realtime_quote_loader,
        cache_only=cache_only,
    )


def _run_many(
    configs: list[WatchlistConfig],
    *,
    output_dir: str,
    start_date: str,
    end_date: str,
    mode: str,
    frame_loader: Callable | None,
    realtime_quote_loader: Callable | None,
    cache_only: bool,
) -> dict[str, dict[str, str]]:
    return {
        config.direction: _run_one(
            config,
            output_dir=f"{output_dir}/{config.direction}",
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            frame_loader=frame_loader,
            realtime_quote_loader=realtime_quote_loader,
            cache_only=cache_only,
        )
        for config in configs
    }


def _run_one(
    config: WatchlistConfig,
    *,
    output_dir: str,
    start_date: str,
    end_date: str,
    mode: str,
    frame_loader: Callable | None,
    realtime_quote_loader: Callable | None,
    cache_only: bool,
) -> dict[str, str]:
    symbols = [item.symbol for item in config.symbols]

    active_frame_loader = frame_loader or load_symbol_frames
    if _accepts_keyword(active_frame_loader, "cache_only"):
        frames = active_frame_loader(symbols, start_date, end_date, cache_only=cache_only)
    else:
        frames = active_frame_loader(symbols, start_date, end_date)

    quote_by_symbol = {}
    if mode == "intraday":
        active_quote_loader = realtime_quote_loader or RealtimeQuoteSource().get_quotes
        quotes = active_quote_loader(symbols)
        quote_by_symbol = {quote["symbol"]: quote for quote in quotes}

    results = []
    for item in config.symbols:
        results.append(
            evaluate_symbol(
                symbol=item.symbol,
                name=item.name,
                instrument_type=item.instrument_type,
                frame=frames[item.symbol],
                mode=mode,
                realtime_quote=quote_by_symbol.get(item.symbol),
            )
        )

    run_date = datetime.strptime(end_date, "%Y%m%d").date().isoformat()
    return write_reports(
        output_dir=output_dir,
        direction=config.direction,
        thesis=config.thesis,
        mode=mode,
        results=results,
        run_date=run_date,
    )


def _accepts_keyword(func: Callable, keyword: str) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return (
        keyword in signature.parameters
        or any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    )
