"""Base strategy class for backtesting."""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from enum import Enum


class Signal(Enum):
    """Trading signal types."""
    BUY = 1
    SELL = -1
    HOLD = 0


@dataclass
class StrategyResult:
    """Result from strategy execution."""
    signal: Signal
    price: Optional[float] = None
    quantity: Optional[float] = None
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class BaseStrategy(ABC):
    """
    Abstract base class for all trading strategies.

    All strategies must inherit from this class and implement
    the generate_signals method.
    """

    def __init__(self, name: str = None):
        self.name = name or self.__class__.__name__
        self._data = None
        self._indicators: Dict[str, Any] = {}

    @property
    def data(self):
        return self._data

    @data.setter
    def data(self, value):
        self._data = value
        self._indicators = {}

    @abstractmethod
    def generate_signals(self, data) -> List[StrategyResult]:
        pass

    def calculate_indicators(self, data) -> Dict[str, Any]:
        return {}

    def get_indicator(self, name: str) -> Any:
        return self._indicators.get(name)

    def set_indicator(self, name: str, value: Any) -> None:
        self._indicators[name] = value

    def validate_data(self, data) -> bool:
        return data is not None and len(data) > 0

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(name='{self.name}')>"
