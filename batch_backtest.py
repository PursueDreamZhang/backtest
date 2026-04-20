"""批量回测脚本 - 遍历年度股票数据运行回测。"""

import os
import pickle
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any

import backtrader as bt
import pandas as pd

from config import BACKTEST_CONFIG, TREND_FOLLOWING_PARAMS
from strategies.trend_following import TrendFollowingStrategy


def load_stock_data(pkl_path: str) -> pd.DataFrame:
    """加载股票数据。"""
    with open(pkl_path, 'rb') as f:
        df = pickle.load(f)
    return df


def run_single_backtest(symbol: str, df: pd.DataFrame, initial_cash: float = 100000.0, commission: float = 0.0003) -> Dict[str, Any]:
    """运行单只股票回测。"""
    try:
        cerebro = bt.Cerebro()
        cerebro.addstrategy(TrendFollowingStrategy, **TREND_FOLLOWING_PARAMS)
        
        # 确保数据格式正确
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        
        data = bt.feeds.PandasData(dataname=df)
        cerebro.adddata(data)
        
        cerebro.broker.setcash(initial_cash)
        cerebro.broker.setcommission(commission=commission)
        
        cerebro.addanalyzer(bt.analyzers.SharpeRatio, _name='sharpe')
        cerebro.addanalyzer(bt.analyzers.DrawDown, _name='drawdown')
        cerebro.addanalyzer(bt.analyzers.Returns, _name='returns')
        cerebro.addanalyzer(bt.analyzers.TradeAnalyzer, _name='trades')
        
        results = cerebro.run()
        strat = results[0]
        final_value = cerebro.broker.getvalue()
        
        # 提取分析结果
        sharpe = strat.analyzers.sharpe.get_analysis()
        drawdown = strat.analyzers.drawdown.get_analysis()
        trades = strat.analyzers.trades.get_analysis()
        
        total_trades = trades.get('total', {}).get('total', 0)
        won = trades.get('won', {}).get('total', 0)
        lost = trades.get('lost', {}).get('total', 0)
        
        pnl = final_value - initial_cash
        pnl_pct = (pnl / initial_cash * 100) if initial_cash else 0
        
        return {
            'symbol': symbol,
            'data_bars': len(df),
            'initial_cash': initial_cash,
            'final_value': round(final_value, 2),
            'pnl': round(pnl, 2),
            'pnl_pct': round(pnl_pct, 2),
            'sharpe': round(sharpe.get('sharperatio', 0), 3) if sharpe.get('sharperatio') else None,
            'max_drawdown': round(drawdown.get('max', {}).get('drawdown', 0), 2),
            'total_trades': total_trades,
            'won': won,
            'lost': lost,
            'win_rate': round(won / total_trades * 100, 1) if total_trades > 0 else 0,
            'status': 'ok',
        }
    except Exception as e:
        return {
            'symbol': symbol,
            'status': 'error',
            'error': str(e),
        }


def batch_backtest_year(year: int, data_dir: str, output_dir: str = None) -> Dict[str, Any]:
    """批量回测某一年所有股票。"""
    year_dir = Path(data_dir) / str(year)
    
    if not year_dir.exists():
        print(f'目录不存在: {year_dir}')
        return {}
    
    pkl_files = list(year_dir.glob('*.pkl'))
    total = len(pkl_files)
    
    print(f'开始批量回测 {year} 年数据，共 {total} 只股票...')
    print('=' * 60)
    
    results = []
    ok_count = 0
    error_count = 0
    no_trade_count = 0
    
    for i, pkl_file in enumerate(pkl_files, 1):
        symbol = pkl_file.stem
        
        try:
            df = load_stock_data(str(pkl_file))
            
            if df is None or df.empty or len(df) < 50:  # 数据不足50条跳过
                results.append({
                    'symbol': symbol,
                    'status': 'skipped',
                    'reason': 'insufficient_data',
                })
                continue
            
            result = run_single_backtest(symbol, df)
            results.append(result)
            
            if result['status'] == 'ok':
                ok_count += 1
                if result['total_trades'] == 0:
                    no_trade_count += 1
            else:
                error_count += 1
            
            # 每100只股票输出进度
            if i % 100 == 0:
                print(f'进度: {i}/{total} ({i/total*100:.1f}%), 成功: {ok_count}, 错误: {error_count}, 无交易: {no_trade_count}')
        
        except Exception as e:
            results.append({
                'symbol': symbol,
                'status': 'error',
                'error': str(e),
            })
            error_count += 1
    
    # 汇总统计
    print('=' * 60)
    print(f'回测完成！')
    print(f'  总数: {total}')
    print(f'  成功: {ok_count}')
    print(f'  错误: {error_count}')
    print(f'  无交易: {no_trade_count}')
    
    # 计算整体收益统计
    profitable = [r for r in results if r.get('status') == 'ok' and r.get('pnl', 0) > 0]
    losing = [r for r in results if r.get('status') == 'ok' and r.get('pnl', 0) < 0]
    traded = [r for r in results if r.get('status') == 'ok' and r.get('total_trades', 0) > 0]
    
    if traded:
        avg_pnl_pct = sum(r['pnl_pct'] for r in traded) / len(traded)
        avg_drawdown = sum(r['max_drawdown'] for r in traded) / len(traded)
        avg_trades = sum(r['total_trades'] for r in traded) / len(traded)
        
        print(f'\n有交易的股票统计 ({len(traded)} 只):')
        print(f'  盈利股票: {len(profitable)} ({len(profitable)/len(traded)*100:.1f}%)')
        print(f'  亏损股票: {len(losing)} ({len(losing)/len(traded)*100:.1f}%)')
        print(f'  平均收益率: {avg_pnl_pct:.2f}%')
        print(f'  平均最大回撤: {avg_drawdown:.2f}%')
        print(f'  平均交易次数: {avg_trades:.1f}')
    
    # 保存结果
    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        result_file = output_path / f'backtest_{year}.json'
        with open(result_file, 'w', encoding='utf-8') as f:
            json.dump({
                'year': year,
                'generated_at': datetime.now().isoformat(),
                'summary': {
                    'total': total,
                    'ok': ok_count,
                    'error': error_count,
                    'no_trade': no_trade_count,
                    'traded': len(traded),
                    'profitable': len(profitable),
                    'losing': len(losing),
                    'avg_pnl_pct': round(avg_pnl_pct, 2) if traded else 0,
                    'avg_drawdown': round(avg_drawdown, 2) if traded else 0,
                    'avg_trades': round(avg_trades, 1) if traded else 0,
                },
                'results': results,
            }, f, ensure_ascii=False, indent=2)
        
        print(f'\n结果已保存到: {result_file}')
    
    return {
        'year': year,
        'summary': {
            'total': total,
            'ok': ok_count,
            'error': error_count,
            'no_trade': no_trade_count,
        },
        'results': results,
    }


if __name__ == '__main__':
    import sys
    
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2020
    data_dir = '/Users/zhangchunfu/Nutstore Files/code/backtest/data/yearly_market_data'
    output_dir = '/Users/zhangchunfu/Nutstore Files/code/backtest/tmp'
    
    batch_backtest_year(year, data_dir, output_dir)
