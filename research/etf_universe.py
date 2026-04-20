from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path


@dataclass(frozen=True)
class EtfUniverseEntry:
    symbol: str
    name: str
    tags: tuple[str, ...]
    is_market_proxy: bool
    is_theme_proxy: bool


def load_etf_universe(path: str | Path) -> list[EtfUniverseEntry]:
    payload = json.loads(Path(path).read_text(encoding='utf-8'))
    items = payload.get('etfs', [])
    result: list[EtfUniverseEntry] = []
    for item in items:
        result.append(
            EtfUniverseEntry(
                symbol=str(item['symbol']).strip(),
                name=str(item['name']).strip(),
                tags=tuple(item.get('tags', [])),
                is_market_proxy=bool(item.get('is_market_proxy', False)),
                is_theme_proxy=bool(item.get('is_theme_proxy', True)),
            )
        )
    return result
