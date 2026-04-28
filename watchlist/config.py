from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path

from data.realtime_quote_source import normalize_cn_symbol


@dataclass(frozen=True)
class WatchSymbol:
    symbol: str
    name: str = ""
    instrument_type: str = "stock"
    role: str = ""


@dataclass(frozen=True)
class WatchlistConfig:
    direction: str
    thesis: str
    symbols: tuple[WatchSymbol, ...]


def _normalize_watch_symbol(symbol: str) -> str:
    normalized = normalize_cn_symbol(symbol)
    if normalized.isdigit() and len(normalized) < 6:
        return normalized.zfill(6)
    return normalized


def _load_one(payload: dict) -> WatchlistConfig:
    symbols = []
    for item in payload.get("symbols", []):
        symbols.append(
            WatchSymbol(
                symbol=_normalize_watch_symbol(item["symbol"]),
                name=str(item.get("name", "")),
                instrument_type=str(item.get("type", "stock")),
                role=str(item.get("role", "")),
            )
        )
    if not symbols:
        raise ValueError("watchlist config 至少需要一个 symbols 条目")
    return WatchlistConfig(
        direction=str(payload.get("direction", "")),
        thesis=str(payload.get("thesis", "")),
        symbols=tuple(symbols),
    )


def load_watchlist_config(path: str | Path) -> WatchlistConfig | list[WatchlistConfig]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "watchlists" in payload:
        configs = [_load_one(item) for item in payload.get("watchlists", [])]
        if not configs:
            raise ValueError("watchlist config 至少需要一个 watchlists 条目")
        return configs
    return _load_one(payload)
