"""导出指定年份区间年初 A 股市值公司列表。"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime

import pandas as pd

# 允许从 scripts/ 目录直接执行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from data.tushare_source import TushareDataSource

_LAST_BAK_CALL_TS = 0.0
_LAST_STOCK_BASIC_CALL_TS = 0.0


def _normalize_ts_code(code: str) -> str:
    code = str(code or '').strip().upper()
    if not code:
        return ''
    if '.' in code:
        return code
    if code.startswith(('8', '4')):
        return f'{code}.BJ'
    if code.startswith(('6', '9')):
        return f'{code}.SH'
    return f'{code}.SZ'


def _resolve_tushare_client():
    try:
        import tushare as ts
    except Exception as e:
        raise RuntimeError(f'未安装 tushare: {e}') from e

    token = TushareDataSource()._resolve_token()
    ts.set_token(token)
    return ts.pro_api()


def _safe_bak_daily(pro, trade_date: str, min_interval_seconds: int = 13):
    global _LAST_BAK_CALL_TS

    # 主动节流，避免触发 5 次/分钟限制
    now = time.time()
    wait = min_interval_seconds - (now - _LAST_BAK_CALL_TS)
    if wait > 0:
        time.sleep(wait)

    try:
        df = pro.bak_daily(trade_date=trade_date)
        _LAST_BAK_CALL_TS = time.time()
        return df
    except Exception as e:
        msg = str(e)
        if '每分钟最多访问' in msg:
            # 兜底：等待一分钟后再试一次
            print(f'  接口限频，等待 60s 后重试: {trade_date}')
            time.sleep(60)
            df = pro.bak_daily(trade_date=trade_date)
            _LAST_BAK_CALL_TS = time.time()
            return df
        raise


def _safe_stock_basic(pro, list_status: str, min_interval_seconds: int = 65):
    global _LAST_STOCK_BASIC_CALL_TS

    now = time.time()
    wait = min_interval_seconds - (now - _LAST_STOCK_BASIC_CALL_TS)
    if wait > 0:
        time.sleep(wait)

    try:
        df = pro.stock_basic(
            exchange='',
            list_status=list_status,
            fields='ts_code,symbol,name,list_date,delist_date',
        )
        _LAST_STOCK_BASIC_CALL_TS = time.time()
        return df
    except Exception as e:
        msg = str(e)
        if '每分钟最多访问该接口1次' in msg:
            print(f'  stock_basic 限频，等待 65s 后重试: list_status={list_status}')
            time.sleep(65)
            df = pro.stock_basic(
                exchange='',
                list_status=list_status,
                fields='ts_code,symbol,name,list_date,delist_date',
            )
            _LAST_STOCK_BASIC_CALL_TS = time.time()
            return df
        raise


def _fetch_stock_basic_map(pro) -> dict[str, dict]:
    stock_basic_map: dict[str, dict] = {}
    for list_status in ['L', 'D', 'P']:
        df = _safe_stock_basic(pro, list_status=list_status)
        if df is None or df.empty:
            continue

        for _, row in df.iterrows():
            ts_code = _normalize_ts_code(row.get('ts_code', ''))
            if not ts_code:
                continue
            stock_basic_map[ts_code] = {
                'symbol': str(row.get('symbol', '') or ''),
                'name': str(row.get('name', '') or ''),
                'list_date': str(row.get('list_date', '') or ''),
                'delist_date': str(row.get('delist_date', '') or ''),
            }
    return stock_basic_map


def _first_open_bak_daily(pro, year: int):
    """在 1 月内逐日探测 bak_daily，找到首个有数据的交易日。"""
    # 年初一般 1/2~1/12 内开市，先探测这段可大幅减少调用次数
    for day in range(2, 13):
        trade_date = f'{year}01{day:02d}'
        df = _safe_bak_daily(pro, trade_date=trade_date)
        if df is not None and not df.empty:
            return trade_date, df
    raise RuntimeError(f'{year} 年 1 月未查询到 bak_daily 数据')


def _fetch_year_bucket(pro, stock_basic_map: dict[str, dict], year: int, min_mv_yi: float, max_mv_yi: float) -> dict:
    trade_date, daily = _first_open_bak_daily(pro, year)
    if daily is None or daily.empty:
        return {'year': year, 'trade_date': trade_date, 'count': 0, 'companies': []}

    # 自动判断 total_mv 单位：
    # 若量级很大（中位数 > 100000）按万元处理，否则按亿元处理。
    daily['total_mv'] = pd.to_numeric(daily['total_mv'], errors='coerce')
    daily['close'] = pd.to_numeric(daily['close'], errors='coerce')
    mv_median = daily['total_mv'].median()
    if mv_median > 100000:
        # 单位万元 -> 转换为亿元
        daily['market_cap_yi'] = (daily['total_mv'] / 10000).round(2)
    else:
        # 单位亿元
        daily['market_cap_yi'] = daily['total_mv'].round(2)

    daily = daily[(daily['market_cap_yi'] >= float(min_mv_yi)) & (daily['market_cap_yi'] <= float(max_mv_yi))].copy()
    daily = daily.sort_values('market_cap_yi', ascending=False)

    companies = []
    for _, row in daily.iterrows():
        ts_code = _normalize_ts_code(row.get('ts_code', ''))
        stock_basic = stock_basic_map.get(ts_code, {})
        companies.append(
            {
                'ts_code': ts_code,
                'symbol': stock_basic.get('symbol') or ts_code.split('.')[0],
                'name': (
                    row['name']
                    if row['name'] == row['name']
                    else stock_basic.get('name', '')
                ),
                'list_date': stock_basic.get('list_date', ''),
                'delist_date': stock_basic.get('delist_date', ''),
                'close': float(row['close']) if row['close'] == row['close'] else None,
                'market_cap_yi': float(row['market_cap_yi']),
            }
        )

    return {'year': year, 'trade_date': trade_date, 'count': len(companies), 'companies': companies}


def export_yearly_market_cap(
    start_year: int = 2020,
    end_year: int = 2026,
    min_mv_yi: float = 30,
    max_mv_yi: float = 1000,
    output_path: str = 'data/report/a_share_mcap_30_1000yi_2020_2026.json',
) -> str:
    pro = _resolve_tushare_client()
    stock_basic_map = _fetch_stock_basic_map(pro)

    data = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'range': {'start_year': start_year, 'end_year': end_year},
        'market_cap_filter_yi': {'min': min_mv_yi, 'max': max_mv_yi},
        'years': [],
    }

    for year in range(start_year, end_year + 1):
        print(f'处理 {year} 年...')
        bucket = _fetch_year_bucket(pro, stock_basic_map, year, min_mv_yi, max_mv_yi)
        print(f'  交易日: {bucket["trade_date"]}, 符合数量: {bucket["count"]}')
        data['years'].append(bucket)

    abs_output = output_path if os.path.isabs(output_path) else os.path.abspath(output_path)
    os.makedirs(os.path.dirname(abs_output), exist_ok=True)
    with open(abs_output, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'导出完成: {abs_output}')
    return abs_output


def main():
    parser = argparse.ArgumentParser(description='导出指定年份区间年初 A 股市值 30-1000 亿公司列表')
    parser.add_argument('--start-year', type=int, default=2020)
    parser.add_argument('--end-year', type=int, default=2026)
    parser.add_argument('--min-mv-yi', type=float, default=30)
    parser.add_argument('--max-mv-yi', type=float, default=1000)
    parser.add_argument(
        '--output',
        type=str,
        default='data/report/a_share_mcap_30_1000yi_2020_2026.json',
    )
    args = parser.parse_args()

    export_yearly_market_cap(
        start_year=args.start_year,
        end_year=args.end_year,
        min_mv_yi=args.min_mv_yi,
        max_mv_yi=args.max_mv_yi,
        output_path=args.output,
    )


if __name__ == '__main__':
    main()
