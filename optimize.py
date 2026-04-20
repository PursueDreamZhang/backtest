"""参数优化模块。"""

from __future__ import annotations

from datetime import datetime
from itertools import product
from typing import Dict, Iterable, List, Tuple

import backtrader as bt

from config import BACKTEST_CONFIG, TREND_FOLLOWING_PARAMS
from data.mock_source import MockDataSource
from data.fallback_source import FallbackDataSource
from strategies.trend_following import TrendFollowingStrategy


def _load_data(symbol: str, start_date: str, end_date: str, use_mock: bool):
    if use_mock:
        return MockDataSource().get_data(500)
    priority = BACKTEST_CONFIG.get('data_source_priority', ['sina', 'akshare', 'yfinance'])
    return FallbackDataSource(priority=priority).get_data(symbol, start_date, end_date)


def _run_once(df, start_date: str, end_date: str, initial_cash: float, commission: float, params: Dict):
    cerebro = bt.Cerebro()
    cerebro.addstrategy(TrendFollowingStrategy, **params)
    data = bt.feeds.PandasData(
        dataname=df,
        fromdate=datetime.strptime(start_date, '%Y%m%d'),
        todate=datetime.strptime(end_date, '%Y%m%d'),
    )
    cerebro.adddata(data)
    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')

    results = cerebro.run()
    strat = results[0]
    trades = strat.analyzers.trades.get_analysis()

    return {
        'params': params,
        'sharpe': strat.analyzers.sharpe.get_analysis().get('sharperatio') or 0.0,
        'drawdown': strat.analyzers.drawdown.get_analysis()['max']['drawdown'],
        'annual_return': strat.analyzers.returns.get_analysis().get('rnorm100') or 0.0,
        'trades': trades.get('total', {}).get('total', 0),
        'final_value': cerebro.broker.getvalue(),
    }


def optimize_strategy(
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    initial_cash: float | None = None,
    commission: float | None = None,
    use_mock: bool = False,
    breakout_range: Iterable[float] = (0.04, 0.05, 0.06),
    hold_days_range: Iterable[int] = (2, 3, 4),
) -> List[Dict]:
    """穷举优化趋势策略核心参数。"""
    symbol = symbol or BACKTEST_CONFIG['symbol']
    start_date = start_date or BACKTEST_CONFIG['start_date']
    end_date = end_date or BACKTEST_CONFIG['end_date']
    initial_cash = initial_cash if initial_cash is not None else BACKTEST_CONFIG['initial_cash']
    commission = commission if commission is not None else BACKTEST_CONFIG['commission']

    if start_date > end_date:
        raise ValueError(f'start_date ({start_date}) 不能晚于 end_date ({end_date})')

    df = _load_data(symbol, start_date, end_date, use_mock=use_mock)
    if df is None or df.empty:
        raise ValueError('数据为空，无法执行参数优化')

    grid: List[Tuple[float, int]] = list(
        product(breakout_range, hold_days_range)
    )
    print(f'开始参数优化，总组合数: {len(grid)}')

    performance: List[Dict] = []
    for breakout_pct, hold_days in grid:
        params = dict(TREND_FOLLOWING_PARAMS)
        params.update(
            {
                'printlog': False,
                'breakout_pct': float(breakout_pct),
                'hold_days': int(hold_days),
            }
        )
        result = _run_once(df, start_date, end_date, initial_cash, commission, params)
        performance.append(result)

    performance.sort(
        key=lambda x: (x['sharpe'], x['annual_return'], -x['drawdown']),
        reverse=True,
    )

    print(f'\n{"=" * 90}')
    print('Top 10 参数组合（排序：夏普 -> 年化收益 -> 回撤）')
    print(f'{"=" * 90}')
    print(f'{"排名":<5} {"breakout":<10} {"hold_days":<10} {"夏普":<10} {"回撤":<10} {"年化":<10} {"交易数":<8}')
    print(f'{"-" * 90}')

    for i, row in enumerate(performance[:10], 1):
        p = row['params']
        print(
            f"{i:<5} {p['breakout_pct']:<10.2f} {p['hold_days']:<10d} "
            f"{row['sharpe']:<10.3f} {row['drawdown']:<10.2f} {row['annual_return']:<10.2f} {row['trades']:<8d}"
        )

    print(f'{"=" * 90}')
    return performance


if __name__ == '__main__':
    optimize_strategy()
