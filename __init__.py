"""
Backtest - A Python backtesting framework.

This package provides tools for backtesting trading strategies.

Example usage:
    from backtest.strategies import SMAStrategy, RSIStrategy
    from backtest.strategies import BaseStrategy, Signal

    # Create a strategy
    strategy = SMAStrategy(short_window=10, long_window=20)

    # Generate signals
    signals = strategy.generate_signals(data)
"""

try:
    from .strategies import (
        BaseStrategy,
        StrategyResult,
        Signal,
        SMAStrategy,
        RSIStrategy,
    )
except ImportError:
    # Support direct file-style imports during pytest collection.
    from strategies import (
        BaseStrategy,
        StrategyResult,
        Signal,
        SMAStrategy,
        RSIStrategy,
    )

__version__ = '0.1.0'

__all__ = [
    # Strategies
    'BaseStrategy',
    'StrategyResult',
    'Signal',
    'SMAStrategy',
    'RSIStrategy',
]
