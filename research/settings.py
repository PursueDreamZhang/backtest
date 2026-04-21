"""Research-first settings for market regime studies."""

from __future__ import annotations

DATA_SOURCE_PRIORITY = ['tushare', 'sina', 'akshare', 'yfinance']

MARKET_REGIME_PARAMS = {
    'benchmark_windows': [10, 20],
    'relative_strength_windows': [20, 40, 60],
    'momentum_windows': [5, 10, 20],
    'short_ma': 20,
    'long_ma': 40,
    'short_volume_window': 5,
    'long_volume_window': 20,
    'forward_windows': [5, 10, 20],
    'weights': {
        'relative_strength_score': 0.30,
        'momentum_score': 0.25,
        'volume_price_score': 0.25,
        'trend_support_score': 0.10,
        'stability_score': 0.10,
    },
    'market_weights': {
        'trend': 0.25,
        'breadth': 0.25,
        'volume_confirmation': 0.25,
        'cooldown_risk': 0.25,
    },
}
