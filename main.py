"""回测主入口。"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

import backtrader as bt
import pandas as pd

from config import BACKTEST_CONFIG, TREND_FOLLOWING_PARAMS
from data.mock_source import MockDataSource
from data.fallback_source import FallbackDataSource
from strategies.trend_following import TrendFollowingStrategy


def _parse_yyyymmdd(value: str) -> datetime:
    return datetime.strptime(value, '%Y%m%d')


def _load_data(symbol: str, start_date: str, end_date: str, use_mock: bool) -> pd.DataFrame:
    if use_mock:
        return MockDataSource().get_data(500)

    priority = BACKTEST_CONFIG.get('data_source_priority', ['sina', 'akshare', 'yfinance'])
    return FallbackDataSource(priority=priority).get_data(symbol, start_date, end_date)


def _build_cerebro(
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    initial_cash: float,
    commission: float,
    strategy_params: Dict[str, Any],
) -> bt.Cerebro:
    cerebro = bt.Cerebro()
    cerebro.addstrategy(TrendFollowingStrategy, **strategy_params)

    data = bt.feeds.PandasData(
        dataname=df,
        fromdate=_parse_yyyymmdd(start_date),
        todate=_parse_yyyymmdd(end_date),
    )
    cerebro.adddata(data)

    cerebro.broker.setcash(initial_cash)
    cerebro.broker.setcommission(commission=commission)

    cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
    cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
    cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
    return cerebro


def _print_summary(
    symbol: str,
    start_date: str,
    end_date: str,
    initial_cash: float,
    final_value: float,
    df: pd.DataFrame,
    strat: bt.Strategy,
) -> None:
    pnl = final_value - initial_cash
    pnl_pct = (pnl / initial_cash * 100) if initial_cash else 0

    print(f'\n{"=" * 60}')
    print('回测结果:')
    print(f'  股票代码: {symbol}')
    print(
        f'  回测区间: {start_date[:4]}-{start_date[4:6]}-{start_date[6:]} '
        f'~ {end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
    )
    print(f'  数据条数: {len(df)}')
    print(f'  最终资产: {final_value:,.2f}')
    print(f'  总盈亏: {pnl:,.2f} ({pnl_pct:.2f}%)')

    sharpe = strat.analyzers.sharpe.get_analysis()
    if sharpe.get('sharperatio') is not None:
        print(f'  夏普比率: {sharpe["sharperatio"]:.3f}')

    drawdown = strat.analyzers.drawdown.get_analysis()
    print(f'  最大回撤: {drawdown["max"]["drawdown"]:.2f}%')

    trades = strat.analyzers.trades.get_analysis()
    total = trades.get('total', {}).get('total', 0)
    won = trades.get('won', {}).get('total', 0)
    lost = trades.get('lost', {}).get('total', 0)
    if total > 0:
        print(f'  交易次数: {total}, 盈利: {won}, 亏损: {lost}, 胜率: {won / total * 100:.1f}%')
    else:
        print('  交易次数: 0')

    print(f'{"=" * 60}')


def run_backtest(
    symbol: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
    use_mock: bool = False,
):
    """运行回测。"""
    symbol = symbol or BACKTEST_CONFIG['symbol']
    start_date = start_date or BACKTEST_CONFIG['start_date']
    end_date = end_date or BACKTEST_CONFIG['end_date']
    initial_cash = BACKTEST_CONFIG['initial_cash']
    commission = BACKTEST_CONFIG['commission']

    if start_date > end_date:
        raise ValueError(f'start_date ({start_date}) 不能晚于 end_date ({end_date})')

    df = _load_data(symbol, start_date, end_date, use_mock=use_mock)
    if df is None or df.empty:
        raise ValueError('数据为空，无法执行回测')

    cerebro = _build_cerebro(
        df=df,
        start_date=start_date,
        end_date=end_date,
        initial_cash=initial_cash,
        commission=commission,
        strategy_params=TREND_FOLLOWING_PARAMS,
    )

    print('开始回测...')
    results = cerebro.run()
    strat = results[0]

    final_value = cerebro.broker.getvalue()
    _print_summary(symbol, start_date, end_date, initial_cash, final_value, df, strat)

    return results


if __name__ == '__main__':
    run_backtest()
