"""每日持仓与候选观察清单。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import BACKTEST_CONFIG, TREND_FOLLOWING_PARAMS
from data.fallback_source import FallbackDataSource


def _yearly_market_file(symbol: str, year: int) -> Path:
    return Path(PROJECT_ROOT) / 'data' / 'yearly_market_data' / str(year) / f'{symbol}.pkl'


def _load_latest_universe(report_path: str) -> list[dict[str, Any]]:
    with open(report_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    years = payload.get('years', [])
    if not years:
        raise ValueError(f'股票池文件缺少 years: {report_path}')

    latest_year = max(years, key=lambda item: int(item['year']))
    return latest_year.get('companies', [])


def _normalize_symbol(value: str) -> str:
    raw = str(value or '').strip().upper()
    if not raw:
        return ''
    return raw.split('.')[0]


def _load_holdings(holdings_path: str) -> list[dict[str, Any]]:
    with open(holdings_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    positions = payload.get('positions', payload if isinstance(payload, list) else [])
    normalized: list[dict[str, Any]] = []
    for item in positions:
        if isinstance(item, str):
            symbol = _normalize_symbol(item)
            if symbol:
                normalized.append({'symbol': symbol})
            continue

        if isinstance(item, dict):
            symbol = _normalize_symbol(item.get('symbol') or item.get('ts_code'))
            if symbol:
                entry = dict(item)
                entry['symbol'] = symbol
                normalized.append(entry)

    return normalized


def _fetch_recent_data(ds: FallbackDataSource, symbol: str, lookback_days: int, end_date: str) -> pd.DataFrame | None:
    start_date = (datetime.strptime(end_date, '%Y%m%d') - timedelta(days=lookback_days)).strftime('%Y%m%d')

    yearly_frames = []
    for year in range(int(start_date[:4]), int(end_date[:4]) + 1):
        yearly_file = _yearly_market_file(symbol, year)
        if yearly_file.exists():
            try:
                yearly_frames.append(pd.read_pickle(yearly_file).sort_index())
            except Exception:
                pass

    if yearly_frames:
        merged = pd.concat(yearly_frames)
        merged = merged[~merged.index.duplicated(keep='last')].sort_index()
        sliced = ds._slice(merged, start_date, end_date)
        if sliced is not None and not sliced.empty:
            return sliced

    try:
        df = ds.get_data(symbol, start_date, end_date, use_cache=True)
    except Exception as e:
        print(f'获取失败 {symbol}: {e}')
        return None

    if df is None or df.empty:
        return None
    return df.sort_index()


def evaluate_watch_candidate(df: pd.DataFrame, params: dict[str, Any]) -> dict[str, Any] | None:
    min_bars = max(params['surge_period'], params['ma_period'], params['support_lookback'], 20)
    if df is None or df.empty or len(df) < min_bars:
        return None

    work = df.copy().sort_index()
    work['ma20'] = work['close'].rolling(params['ma_short_period']).mean()
    work['ma40'] = work['close'].rolling(params['ma_period']).mean()
    work['ma10'] = work['close'].rolling(params['ma_exit_period']).mean()
    work['box_low'] = work['low'].rolling(params['support_lookback']).min()
    work['vol_ma5'] = work['volume'].rolling(5).mean()
    work['vol_ma20'] = work['volume'].rolling(20).mean()
    work['high_30'] = work['high'].rolling(params['surge_period']).max()
    work['low_30'] = work['low'].rolling(params['surge_period']).min()
    work['peak_30'] = work['high_30']

    had_surge = False
    surge_peak = 0.0
    in_position = False
    buy_price = None
    structure_stop = None
    days_held = 0

    current_snapshot: dict[str, Any] | None = None

    for idx in range(min_bars - 1, len(work)):
        row = work.iloc[idx]
        prev_close = float(work.iloc[idx - 1]['close'])
        close_price = float(row['close'])
        ma20 = float(row['ma20'])
        ma40 = float(row['ma40'])
        ma10 = float(row['ma10']) if not pd.isna(row['ma10']) else None
        box_low = float(row['box_low'])
        vol_ma5 = float(row['vol_ma5']) if not pd.isna(row['vol_ma5']) else None
        vol_ma20 = float(row['vol_ma20']) if not pd.isna(row['vol_ma20']) else None
        high_30 = float(row['high_30'])
        low_30 = float(row['low_30'])
        surge_30 = (high_30 - low_30) / low_30 if low_30 > 0 else 0.0

        if not in_position:
            if surge_30 >= params['surge_threshold']:
                had_surge = True
                surge_peak = float(row['peak_30'])

            distance_from_peak = (surge_peak - close_price) / surge_peak if had_surge and surge_peak > 0 else 0.0
            cond_pulled_back = had_surge and distance_from_peak > 0.05

            support_levels = [ma20, ma40, box_low]
            support_distances = [abs(close_price - level) / level for level in support_levels if level > 0]
            min_support_distance = min(support_distances) if support_distances else 999.0
            cond_near_support = min_support_distance <= params['support_range']

            cond_volume_shrink = (
                vol_ma5 is not None and vol_ma20 is not None and vol_ma5 <= vol_ma20 * params['volume_shrink_ratio']
            )
            intraday_change = (float(row['high']) - prev_close) / prev_close if prev_close > 0 else 0.0
            cond_breakout = intraday_change >= params['breakout_pct']

            current_snapshot = {
                'latest_date': work.index[idx].strftime('%Y-%m-%d'),
                'close': round(close_price, 2),
                'surge_30_pct': round(surge_30 * 100, 2),
                'distance_from_peak_pct': round(distance_from_peak * 100, 2),
                'support_distance_pct': round(min_support_distance * 100, 2),
                'ma20': round(ma20, 2),
                'ma40': round(ma40, 2),
                'box_low': round(box_low, 2),
                'stage1_strong': had_surge,
                'stage1_current_surge': surge_30 >= params['surge_threshold'],
                'stage2_pulled_back': cond_pulled_back,
                'stage2_near_support': cond_near_support,
            }

            if had_surge and cond_pulled_back and cond_near_support and cond_volume_shrink and cond_breakout:
                in_position = True
                buy_price = close_price
                days_held = 0
                structure_stop = min(ma40, box_low, close_price * 0.98)
                had_surge = False
                surge_peak = 0.0
        else:
            days_held += 1
            profit_pct = (close_price - buy_price) / buy_price if buy_price else 0.0
            daily_drop = (prev_close - close_price) / prev_close if prev_close > 0 else 0.0

            should_sell = False
            if structure_stop is not None and close_price <= structure_stop:
                should_sell = True
            elif profit_pct <= -params['stop_loss']:
                should_sell = True
            elif days_held >= params['hold_days'] and profit_pct < params['profit_threshold']:
                should_sell = True
            elif profit_pct > 0 and ma10 is not None and close_price < ma10:
                should_sell = True
            elif daily_drop >= params['drop_threshold']:
                should_sell = True

            if should_sell:
                in_position = False
                buy_price = None
                structure_stop = None
                days_held = 0

    if current_snapshot is None:
        return None

    if in_position:
        return None

    if not current_snapshot['stage1_strong']:
        return None
    if not current_snapshot['stage1_current_surge']:
        return None
    if not current_snapshot['stage2_pulled_back']:
        return None
    if not current_snapshot['stage2_near_support']:
        return None

    return {
        'latest_date': current_snapshot['latest_date'],
        'close': current_snapshot['close'],
        'surge_30_pct': current_snapshot['surge_30_pct'],
        'distance_from_peak_pct': current_snapshot['distance_from_peak_pct'],
        'support_distance_pct': current_snapshot['support_distance_pct'],
        'ma20': current_snapshot['ma20'],
        'ma40': current_snapshot['ma40'],
        'box_low': current_snapshot['box_low'],
    }


def build_daily_watchlist(
    report_path: str,
    holdings_path: str,
    output_path: str,
    lookback_days: int = 180,
    end_date: str | None = None,
) -> dict[str, Any]:
    companies = _load_latest_universe(report_path)
    holdings = _load_holdings(holdings_path)
    end_date = end_date or datetime.now().strftime('%Y%m%d')

    company_map = {_normalize_symbol(item.get('ts_code')): item for item in companies}
    symbols = sorted(company_map.keys())
    priority = BACKTEST_CONFIG.get('data_source_priority', ['tushare', 'sina', 'akshare', 'yfinance'])
    ds = FallbackDataSource(priority=priority)

    held_positions: list[dict[str, Any]] = []
    watch_candidates: list[dict[str, Any]] = []
    holdings_symbols = {_normalize_symbol(item['symbol']) for item in holdings}

    for index, symbol in enumerate(symbols, start=1):
        df = _fetch_recent_data(ds, symbol, lookback_days=lookback_days, end_date=end_date)
        latest_metrics = evaluate_watch_candidate(df, TREND_FOLLOWING_PARAMS) if df is not None else None
        company = company_map[symbol]
        base_info = {
            'symbol': symbol,
            'ts_code': company.get('ts_code', ''),
            'name': company.get('name', ''),
        }

        if symbol in holdings_symbols:
            held_item = next(item for item in holdings if _normalize_symbol(item['symbol']) == symbol)
            entry = {**base_info, **held_item}
            if df is not None and not df.empty:
                entry['latest_date'] = df.index[-1].strftime('%Y-%m-%d')
                entry['close'] = round(float(df.iloc[-1]['close']), 2)
            held_positions.append(entry)

        if latest_metrics is not None and symbol not in holdings_symbols:
            watch_candidates.append({**base_info, **latest_metrics})

        if index % 200 == 0:
            print(f'进度: {index}/{len(symbols)}, 已持有命中 {len(held_positions)}, 候选观察 {len(watch_candidates)}')

    payload = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'end_date': end_date,
        'report_path': os.path.abspath(report_path),
        'holdings_path': os.path.abspath(holdings_path),
        'summary': {
            'universe_size': len(symbols),
            'held_positions': len(held_positions),
            'watch_candidates': len(watch_candidates),
        },
        'held_positions': sorted(held_positions, key=lambda item: item['symbol']),
        'watch_candidates': sorted(
            watch_candidates,
            key=lambda item: (-item['surge_30_pct'], item['support_distance_pct'], item['symbol']),
        ),
    }

    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    return payload


def main():
    parser = argparse.ArgumentParser(description='生成每日持仓与候选观察 JSON')
    parser.add_argument('--report', default='data/report/a_share_mcap_30_1000yi_2020_2026.json')
    parser.add_argument('--holdings', default='config/holdings.json')
    parser.add_argument('--output', default=f'tmp/daily_watchlist_{datetime.now().strftime("%Y%m%d")}.json')
    parser.add_argument('--lookback-days', type=int, default=180)
    parser.add_argument('--end-date', default=None, help='YYYYMMDD，默认今天')
    args = parser.parse_args()

    payload = build_daily_watchlist(
        report_path=args.report,
        holdings_path=args.holdings,
        output_path=args.output,
        lookback_days=args.lookback_days,
        end_date=args.end_date,
    )

    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))
    print(f'输出文件: {os.path.abspath(args.output)}')


if __name__ == '__main__':
    main()
