from __future__ import annotations

from datetime import datetime, timedelta
import inspect
from typing import Callable

from data.realtime_quote_source import RealtimeQuoteSource
from research.data_loader import load_symbol_frames

from .config import WatchlistConfig, load_watchlist_config
from .reporting import _summary, write_overview_reports, write_reports
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
    paths = {}
    overview_reports = []
    shared_frames = None
    shared_quotes = None
    shared_run_date = datetime.strptime(end_date, "%Y%m%d").date().isoformat()
    unique_symbols = _unique_symbols(configs)

    if unique_symbols:
        shared_frames, shared_quotes = _load_shared_inputs(
            symbols=unique_symbols,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            frame_loader=frame_loader,
            realtime_quote_loader=realtime_quote_loader,
            cache_only=cache_only,
        )

    for config in configs:
        run_result = _evaluate_one(
            config,
            start_date=start_date,
            end_date=end_date,
            mode=mode,
            frame_loader=frame_loader,
            realtime_quote_loader=realtime_quote_loader,
            cache_only=cache_only,
            preloaded_frames=shared_frames,
            preloaded_quotes=shared_quotes,
        )
        paths[config.direction] = write_reports(
            output_dir=f"{output_dir}/{config.direction}",
            direction=config.direction,
            thesis=config.thesis,
            mode=mode,
            results=run_result["results"],
            run_date=run_result["run_date"],
        )
        overview_reports.append(
            {
                "direction": config.direction,
                "summary": run_result["summary"],
                "items": run_result["results"],
            }
        )

    paths["overview"] = write_overview_reports(
        output_dir=output_dir,
        reports=overview_reports,
        mode=mode,
        run_date=shared_run_date,
    )
    return paths


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
    run_result = _evaluate_one(
        config,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        frame_loader=frame_loader,
        realtime_quote_loader=realtime_quote_loader,
        cache_only=cache_only,
    )
    return write_reports(
        output_dir=output_dir,
        direction=config.direction,
        thesis=config.thesis,
        mode=mode,
        results=run_result["results"],
        run_date=run_result["run_date"],
    )


def _evaluate_one(
    config: WatchlistConfig,
    *,
    start_date: str,
    end_date: str,
    mode: str,
    frame_loader: Callable | None,
    realtime_quote_loader: Callable | None,
    cache_only: bool,
    preloaded_frames: dict | None = None,
    preloaded_quotes: dict | None = None,
) -> dict:
    symbols = [item.symbol for item in config.symbols]
    frames = preloaded_frames if preloaded_frames is not None else _load_frames(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        frame_loader=frame_loader,
        cache_only=cache_only,
    )

    quote_by_symbol = preloaded_quotes if preloaded_quotes is not None else _load_quotes(
        symbols=symbols,
        mode=mode,
        realtime_quote_loader=realtime_quote_loader,
    )

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
                expected_end_date=end_date,
            )
        )

    run_date = datetime.strptime(end_date, "%Y%m%d").date().isoformat()
    return {
        "results": results,
        "summary": _summary(results, mode),
        "run_date": run_date,
    }


def _unique_symbols(configs: list[WatchlistConfig]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for config in configs:
        for item in config.symbols:
            if item.symbol in seen:
                continue
            seen.add(item.symbol)
            symbols.append(item.symbol)
    return symbols


def _load_shared_inputs(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    mode: str,
    frame_loader: Callable | None,
    realtime_quote_loader: Callable | None,
    cache_only: bool,
) -> tuple[dict, dict]:
    frames = _load_frames(
        symbols=symbols,
        start_date=start_date,
        end_date=end_date,
        mode=mode,
        frame_loader=frame_loader,
        cache_only=cache_only,
    )
    quote_by_symbol = _load_quotes(
        symbols=symbols,
        mode=mode,
        realtime_quote_loader=realtime_quote_loader,
    )
    return frames, quote_by_symbol


def _load_frames(
    *,
    symbols: list[str],
    start_date: str,
    end_date: str,
    mode: str,
    frame_loader: Callable | None,
    cache_only: bool,
):
    active_frame_loader = frame_loader or load_symbol_frames
    prefer_cache_for_current_day = mode == "close_confirmed" and end_date == datetime.now().strftime("%Y%m%d")
    history_end_date = end_date
    if mode == "intraday" and end_date == datetime.now().strftime("%Y%m%d"):
        history_end_date = (datetime.strptime(end_date, "%Y%m%d") - timedelta(days=1)).strftime("%Y%m%d")
    if _accepts_keyword(active_frame_loader, "cache_only"):
        frame_kwargs = {"cache_only": cache_only}
        if prefer_cache_for_current_day and _accepts_keyword(active_frame_loader, "prefer_cache_for_current_day"):
            frame_kwargs["prefer_cache_for_current_day"] = prefer_cache_for_current_day
        return active_frame_loader(symbols, start_date, history_end_date, **frame_kwargs)
    return active_frame_loader(symbols, start_date, history_end_date)


def _load_quotes(
    *,
    symbols: list[str],
    mode: str,
    realtime_quote_loader: Callable | None,
) -> dict:
    if mode != "intraday":
        return {}
    active_quote_loader = realtime_quote_loader or RealtimeQuoteSource().get_quotes
    quotes = active_quote_loader(symbols)
    return {quote["symbol"]: quote for quote in quotes}


def _accepts_keyword(func: Callable, keyword: str) -> bool:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return False
    return (
        keyword in signature.parameters
        or any(param.kind == inspect.Parameter.VAR_KEYWORD for param in signature.parameters.values())
    )
