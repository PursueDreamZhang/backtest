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


def load_watchlist_config(path: str | Path) -> WatchlistConfig:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    symbols = []
    for item in payload.get("symbols", []):
        symbols.append(
            WatchSymbol(
                symbol=normalize_cn_symbol(item["symbol"]),
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
