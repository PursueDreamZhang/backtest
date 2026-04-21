"""Relative Strength Index (RSI) strategy."""

from typing import List
import pandas as pd

from .base import BaseStrategy, StrategyResult, Signal


class RSIStrategy(BaseStrategy):
    def __init__(
        self,
        period: int = 14,
        oversold: float = 30.0,
        overbought: float = 70.0,
        price_column: str = 'close',
        name: str = None
    ):
        super().__init__(name)
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.price_column = price_column

        if oversold >= overbought:
            raise ValueError(
                f"oversold ({oversold}) must be less than "
                f"overbought ({overbought})"
            )

        if not (0 <= oversold <= 100 and 0 <= overbought <= 100):
            raise ValueError("Thresholds must be between 0 and 100")

    def validate_data(self, data) -> bool:
        if not super().validate_data(data):
            return False
        if isinstance(data, pd.DataFrame):
            return self.price_column in data.columns
        return True

    def calculate_indicators(self, data) -> dict:
        if isinstance(data, pd.DataFrame):
            prices = data[self.price_column]
            delta = prices.diff()
            gains = delta.where(delta > 0, 0.0)
            losses = (-delta).where(delta < 0, 0.0)
            avg_gains = gains.rolling(window=self.period).mean()
            avg_losses = losses.rolling(window=self.period).mean()
            rs = avg_gains / avg_losses
            rsi = 100.0 - (100.0 / (1.0 + rs))
            return {'rsi': rsi}
        return {}

    def generate_signals(self, data) -> List[StrategyResult]:
        if not self.validate_data(data):
            raise ValueError("Invalid data provided to strategy")

        indicators = self.calculate_indicators(data)
        rsi = indicators['rsi']

        results = []
        for i in range(len(data)):
            rsi_value = rsi.iloc[i]

            if pd.isna(rsi_value):
                results.append(StrategyResult(
                    signal=Signal.HOLD,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'rsi': None}
                ))
            elif rsi_value < self.oversold:
                results.append(StrategyResult(
                    signal=Signal.BUY,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'rsi': rsi_value}
                ))
            elif rsi_value > self.overbought:
                results.append(StrategyResult(
                    signal=Signal.SELL,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'rsi': rsi_value}
                ))
            else:
                results.append(StrategyResult(
                    signal=Signal.HOLD,
                    price=data[self.price_column].iloc[i] if isinstance(data, pd.DataFrame) else None,
                    metadata={'rsi': rsi_value}
                ))

        return results

    def __repr__(self) -> str:
        return (
            f"<RSIStrategy(period={self.period}, "
            f"oversold={self.oversold}, overbought={self.overbought})>"
        )
