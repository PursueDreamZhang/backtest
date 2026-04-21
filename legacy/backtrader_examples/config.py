"""旧 backtrader demo 配置。"""

BACKTEST_CONFIG = {
    'symbol': '002149',
    'start_date': '20200101',
    'end_date': '20260402',
    'initial_cash': 100000.0,
    'commission': 0.0003,
    'data_source_priority': ['tushare', 'sina', 'akshare', 'yfinance'],
}

TREND_FOLLOWING_PARAMS = {
    'surge_period': 30,
    'surge_threshold': 0.50,
    'ma_period': 40,
    'ma_short_period': 20,
    'ma_exit_period': 10,
    'support_lookback': 20,
    'support_range': 0.05,
    'breakout_pct': 0.05,
    'volume_shrink_ratio': 0.80,
    'stop_loss': 0.10,
    'profit_threshold': 0.03,
    'hold_days': 2,
    'drop_threshold': 0.05,
    'risk_per_trade': 0.02,
    'position_pct_max': 0.15,
    'printlog': True,
}
