from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_CACHE_DIR = PROJECT_ROOT / 'tmp' / 'fallback_cache'

from config import BACKTEST_CONFIG, MARKET_REGIME_PARAMS
from data.fallback_source import FallbackDataSource
from research.etf_universe import load_etf_universe
from research.market_regime import (
    build_daily_state,
    build_feature_table,
    build_leaderboard,
    build_summary,
)


def load_symbol_frames(symbols: list[str], start_date: str, end_date: str):
    priority = BACKTEST_CONFIG.get('data_source_priority', ['tushare', 'sina', 'akshare', 'yfinance'])
    source = FallbackDataSource(priority=priority, cache_dir=str(DEFAULT_CACHE_DIR))
    frames = {}
    for symbol in symbols:
        frames[symbol] = source.get_data(symbol, start_date, end_date, use_cache=True)
    return frames


def run_research(universe_path: str, output_dir: str, start_date: str, end_date: str):
    universe = load_etf_universe(universe_path)
    symbols = [item.symbol for item in universe]
    market_proxies = [item.symbol for item in universe if item.is_market_proxy]
    benchmark_symbol = market_proxies[0]

    frames = load_symbol_frames(symbols, start_date, end_date)
    features = build_feature_table(frames, benchmark_symbol=benchmark_symbol, params=MARKET_REGIME_PARAMS)
    leaderboard = build_leaderboard(features)
    daily_state = build_daily_state(frames, leaderboard, benchmark_symbol=benchmark_symbol, params=MARKET_REGIME_PARAMS)
    summary = build_summary(daily_state, leaderboard, frames[benchmark_symbol], MARKET_REGIME_PARAMS['forward_windows'])

    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    daily_state_path = output / 'daily_state.csv'
    leaderboard_path = output / 'leaderboard.csv'
    summary_path = output / 'summary.json'

    daily_state.to_csv(daily_state_path, index=False)
    leaderboard.to_csv(leaderboard_path, index=False)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')

    return {
        'daily_state_path': str(daily_state_path),
        'leaderboard_path': str(leaderboard_path),
        'summary_path': str(summary_path),
    }


def main():
    parser = argparse.ArgumentParser(description='运行市场阶段与主线 ETF 离线研究')
    parser.add_argument('--universe', required=True, help='ETF 代理池配置文件')
    parser.add_argument('--start-date', required=True, help='开始日期，格式 YYYYMMDD')
    parser.add_argument('--end-date', required=True, help='结束日期，格式 YYYYMMDD')
    parser.add_argument('--output-dir', required=True, help='输出目录')
    args = parser.parse_args()

    result = run_research(
        universe_path=args.universe,
        output_dir=args.output_dir,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
