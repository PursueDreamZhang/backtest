"""兼容层：保留旧入口，内部复用新模块实现。"""

from strategies.trend_following import TrendFollowingStrategy
from data.mock_source import MockDataSource
from data.sina_source import SinaDataSource
from data.fallback_source import FallbackDataSource
from config import BACKTEST_CONFIG
from main import run_backtest


def generate_mock_data(days=500):
    """兼容旧接口：生成模拟数据。"""
    return MockDataSource().get_data(days=days)


def get_stock_data_sina(symbol, start_date, end_date):
    """兼容旧接口：从新浪获取数据。"""
    return SinaDataSource().get_data(symbol, start_date, end_date, use_cache=False)


def get_stock_data(symbol, start_date, end_date):
    """兼容旧接口：按默认优先级自动降级获取。"""
    priority = BACKTEST_CONFIG.get('data_source_priority', ['sina', 'akshare', 'yfinance'])
    return FallbackDataSource(priority=priority).get_data(symbol, start_date, end_date, use_cache=True)


def main():
    """兼容旧脚本执行入口。"""
    run_backtest()


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
