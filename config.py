"""策略与回测配置。"""

# 回测基础配置
BACKTEST_CONFIG = {
    'symbol': '002149',
    'start_date': '20200101',
    'end_date': '20260402',
    'initial_cash': 100000.0,
    'commission': 0.0003,
    'data_source_priority': ['tushare', 'sina', 'akshare', 'yfinance'],
}

# 趋势跟踪策略参数（与 strategies/trend_following.py 的默认参数保持一致）
TREND_FOLLOWING_PARAMS = {
    # 买入参数
    'surge_period': 30,
    'surge_threshold': 0.50,
    'ma_period': 40,
    'ma_short_period': 20,
    'ma_exit_period': 10,
    'support_lookback': 20,
    'support_range': 0.05,
    'breakout_pct': 0.05,
    'volume_shrink_ratio': 0.80,

    # 卖出参数
    'stop_loss': 0.10,
    'profit_threshold': 0.03,
    'hold_days': 2,
    'drop_threshold': 0.05,

    # 仓位管理
    'risk_per_trade': 0.02,
    'position_pct_max': 0.15,

    # 日志
    'printlog': True,
}

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
        'relative_strength': 0.30,
        'momentum': 0.25,
        'volume_price': 0.25,
        'trend_support': 0.10,
        'stability': 0.10,
    },
    'market_weights': {
        'trend': 0.25,
        'breadth': 0.25,
        'volume_confirmation': 0.25,
        'cooldown_risk': 0.25,
    },
}
