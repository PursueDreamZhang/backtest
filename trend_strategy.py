"""兼容入口：旧趋势策略兼容层已迁入 legacy/backtrader_examples。"""

from legacy.backtrader_examples.trend_strategy import (
    TrendFollowingStrategy,
    generate_mock_data,
    get_stock_data_sina,
    get_stock_data,
    run_backtest,
    main,
)

__all__ = [
    'TrendFollowingStrategy',
    'generate_mock_data',
    'get_stock_data_sina',
    'get_stock_data',
    'run_backtest',
    'main',
]

if __name__ == '__main__':
    main()
