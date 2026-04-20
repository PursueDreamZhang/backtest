"""
Trading strategies module.

This module provides base classes and example strategies for backtesting.

Example usage:
    from backtest.strategies import SMAStrategy, RSIStrategy

    # Create SMA crossover strategy
    sma_strategy = SMAStrategy(short_window=10, long_window=20)

    # Create RSI mean reversion strategy
    rsi_strategy = RSIStrategy(period=14, oversold=30, overbought=70)

    # Generate signals
    signals = sma_strategy.generate_signals(data)
"""

from .base import BaseStrategy, StrategyResult, Signal
from .sma import SMAStrategy
from .rsi import RSIStrategy

try:
    from .trend_following import TrendFollowingStrategy
except ImportError:
    TrendFollowingStrategy = None

__all__ = [
    # Base classes
    'BaseStrategy',
    'StrategyResult',
    'Signal',

    # Concrete strategies
    'SMAStrategy',
    'RSIStrategy',
]

if TrendFollowingStrategy is not None:
    __all__.append('TrendFollowingStrategy')
