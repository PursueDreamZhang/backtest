from __future__ import annotations

from pathlib import Path

from data.fallback_source import FallbackDataSource

from .settings import DATA_SOURCE_PRIORITY

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CACHE_DIR = PROJECT_ROOT / 'tmp' / 'fallback_cache'


def load_symbol_frames(
    symbols: list[str],
    start_date: str,
    end_date: str,
    *,
    use_cache: bool = True,
    cache_only: bool = False,
    prefer_cache_for_current_day: bool = False,
    cache_dir: str | None = None,
    priority: list[str] | None = None,
):
    source = FallbackDataSource(
        priority=priority or DATA_SOURCE_PRIORITY,
        cache_dir=str(cache_dir or DEFAULT_CACHE_DIR),
    )
    return source.get_data_batch(
        symbols,
        start_date,
        end_date,
        use_cache=use_cache,
        cache_only=cache_only,
        prefer_cache_for_current_day=prefer_cache_for_current_day,
    )
