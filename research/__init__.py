"""Research-first entrypoints for market regime studies."""

from .etf_universe import EtfUniverseEntry, load_etf_universe
from .pipeline import run_research
from .settings import DATA_SOURCE_PRIORITY, MARKET_REGIME_PARAMS

__all__ = [
    'EtfUniverseEntry',
    'load_etf_universe',
    'run_research',
    'DATA_SOURCE_PRIORITY',
    'MARKET_REGIME_PARAMS',
]
