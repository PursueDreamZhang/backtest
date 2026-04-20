"""Simple Moving Average (SMA) crossover strategy."""

from typing import List
import pandas as pd

from .base import BaseStrategy, StrategyResult, Signal


class SMAStrategy(BaseStrategy):
    """
    SMA Crossover Strategy.

    Generates buy signals when short SMA crosses above long SMA,
    and sell signals when short SMA crosses below long SMA.
    """

    def __init__(
        self,
        short_window: int = 10,
        long_window: int = 20,
        price_column: str = 'close',
        name: str = None
    ):
        """
        Initialize SMA strategy.

        Args:
            short_window: Short-term SMA period (default: 10)
            long_window: Long-term SMA period (default: 20)
            price_column: Column to use for price (default: 'close')
            name: Strategy name
        """
        super().__init__(name)
        self.short_window = short_window
        self.long_window = long_window
        self.price_column = price_column

        if short_window >= long_window:
            raise ValueError(
                f"short_window ({short_window}) must be less than "
                f"long_window ({long_window})"
            )

    def validate_data(self, data) -> bool:
        """Validate data has required columns."""
        if not super().validate_data(data):
            return False
        if isinstance(data, pd.DataFrame):
            return self.price_column in data.columns
        return True

    def calculate_indicators(self, data) -> dict:
        """Calculate SMA indicators."""
        if isinstance(data, pd.DataFrame):
            prices = data[self.price_column]

            short_sma = prices.rolling(window=self.short_window).mean()
            long_sma = prices.rolling(window=self.long_window).mean()

            return {
                'short_sma': short_sma,
                'long_sma': long_sma,
            }
        return {}

    def generate_signals(self, data) -> List[StrategyResult]:
        """
        Generate trading signals based on SMA crossover.

        Args:
            data: Market data DataFrame with price column

        Returns:
            List of StrategyResult objects
        """
        if not self.validate_data(data):
            raise ValueError("Invalid data provided to strategy")

        indicators = self.calculate_indicators(data)
        short_sma = indicators['short_sma']
        long_sma = indicators['long_sma']

        # Calculate crossover signals
        # 1 when short crosses above long, -1 when crosses below
        crossover = (short_sma > long_sma).astype(int) - (short_sma < long_sma).astype(int)
        crossover_diff = crossover.diff()

        results = []
        for i in range(len(data)):
            if pd.isna(crossover_diff.iloc[i]):
                # Not enough data for signal
                results.append(StrategyResult(
                    signal=Signal.HOLD,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'short_sma': short_sma.iloc[i], 'long_sma': long_sma.iloc[i]}
                ))
            elif crossover_diff.iloc[i] > 0:
                # Short SMA crossed above long SMA - BUY signal
                results.append(StrategyResult(
                    signal=Signal.BUY,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'short_sma': short_sma.iloc[i], 'long_sma': long_sma.iloc[i]}
                ))
            elif crossover_diff.iloc[i] < 0:
                # Short SMA crossed below long SMA - SELL signal
                results.append(StrategyResult(
                    signal=Signal.SELL,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'short_sma': short_sma.iloc[i], 'long_sma': long_sma.iloc[i]}
                ))
            else:
                # No crossover
                results.append(StrategyResult(
                    signal=Signal.HOLD,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'short_sma': short_sma.iloc[i], 'long_sma': long_sma.iloc[i]}
                ))

        return results

    def __repr__(self) -> str:
        return (
            f"<SMAStrategy(short_window={self.short_window}, "
            f"long_window={self.long_window})>"
        )
