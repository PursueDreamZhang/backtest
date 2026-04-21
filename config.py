"""兼容配置入口。

研究相关参数已迁入 research/settings.py。
旧回测相关参数已迁入 legacy/backtrader_examples/config.py。
"""

from legacy.backtrader_examples.config import BACKTEST_CONFIG, TREND_FOLLOWING_PARAMS
from research.settings import MARKET_REGIME_PARAMS, DATA_SOURCE_PRIORITY

__all__ = [
    'BACKTEST_CONFIG',
    'TREND_FOLLOWING_PARAMS',
    'MARKET_REGIME_PARAMS',
    'DATA_SOURCE_PRIORITY',
]
