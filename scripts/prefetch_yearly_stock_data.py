"""按年份分批预取市场历史数据（带随机停顿），用于后续回测。"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import datetime

import pandas as pd

# 允许从 scripts/ 目录直接执行
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import BACKTEST_CONFIG
from data.fallback_source import FallbackDataSource


def _load_yearly_list(path: str) -> dict:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def _to_symbol(code: str) -> str:
    # ts_code: 000001.SZ -> 000001
    return code.split('.')[0]


def _classify_item_availability(item: dict, start_date: str, end_date: str) -> str | None:
    list_date = str(item.get('list_date', '') or '').strip()
    delist_date = str(item.get('delist_date', '') or '').strip()

    if list_date and list_date > end_date:
        return 'not_listed_yet'
    if delist_date and delist_date < start_date:
        return 'delisted_before_range'
    return None


def _sleep_random(min_s: float, max_s: float, hint: str = ''):
    if max_s <= 0:
        return
    duration = random.uniform(min_s, max_s)
    if hint:
        print(f'{hint}，休眠 {duration:.2f}s')
    time.sleep(duration)


def _fetch_with_retry(ds: FallbackDataSource, symbol: str, start_date: str, end_date: str, retries: int) -> pd.DataFrame | None:
    last_err = None
    for i in range(1, retries + 1):
        try:
            df = ds.get_data(symbol, start_date, end_date, use_cache=True)
            if df is not None and not df.empty:
                return df
            last_err = '空数据'
        except Exception as e:
            last_err = str(e)
        if i < retries:
            _sleep_random(1.5, 3.5, f'重试前等待（{symbol} 第{i}次失败: {last_err}）')
    print(f'获取失败: {symbol} ({start_date}-{end_date}), 原因: {last_err}')
    return None


def _load_from_fallback_cache(ds: FallbackDataSource, symbol: str, start_date: str, end_date: str) -> pd.DataFrame | None:
    cache_file = os.path.join(ds.cache_dir, f'fallback_{symbol}.pkl')
    if not os.path.exists(cache_file):
        return None

    try:
        cached_df = pd.read_pickle(cache_file).sort_index()
    except Exception as e:
        print(f'缓存读取失败: {symbol}, {e}')
        return None

    if cached_df is None or cached_df.empty:
        return None

    sliced = ds._slice(cached_df, start_date, end_date)
    if sliced is None or sliced.empty:
        return None
    return sliced


def _cache_starts_after_range(ds: FallbackDataSource, symbol: str, end_date: str) -> bool:
    cache_file = os.path.join(ds.cache_dir, f'fallback_{symbol}.pkl')
    if not os.path.exists(cache_file):
        return False

    try:
        cached_df = pd.read_pickle(cache_file).sort_index()
    except Exception:
        return False

    if cached_df is None or cached_df.empty:
        return False
    return cached_df.index.min().strftime('%Y%m%d') > end_date


def _append_error(error_file: str, message: str):
    os.makedirs(os.path.dirname(error_file), exist_ok=True)
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(error_file, 'a', encoding='utf-8') as f:
        f.write(f'[{ts}] {message}\n')


def prefetch(
    input_json: str,
    output_dir: str,
    batch_size: int = 20,
    min_request_sleep: float = 0.8,
    max_request_sleep: float = 2.2,
    min_batch_sleep: float = 8.0,
    max_batch_sleep: float = 18.0,
    retries: int = 3,
    overwrite: bool = False,
    checkpoint_every: int = 1,
    cache_only: bool = False,
):
    payload = _load_yearly_list(input_json)
    years = payload.get('years', [])
    if not years:
        raise ValueError('输入文件不包含 years 数据')

    priority = BACKTEST_CONFIG.get('data_source_priority', ['tushare', 'sina', 'akshare', 'yfinance'])
    ds = FallbackDataSource(priority=priority)

    os.makedirs(output_dir, exist_ok=True)
    checkpoint_file = os.path.join(output_dir, 'prefetch_checkpoint.json')
    error_file = os.path.join(output_dir, 'prefetch_errors.log')

    def save_checkpoint(year: int, idx: int, total: int, ok: int, skipped: int, filtered: int, failed: int, ts_code: str):
        payload = {
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'year': year,
            'processed': idx,
            'total': total,
            'ok': ok,
            'skipped': skipped,
            'filtered': filtered,
            'failed': failed,
            'last_ts_code': ts_code,
        }
        with open(checkpoint_file, 'w', encoding='utf-8') as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    summary = {
        'generated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'input_file': os.path.abspath(input_json),
        'data_source_priority': priority,
        'years': {},
    }

    for year_block in years:
        year = int(year_block['year'])
        companies = year_block.get('companies', [])
        year_dir = os.path.join(output_dir, str(year))
        os.makedirs(year_dir, exist_ok=True)

        start_date = f'{year}0101'
        end_date = f'{year}1231'

        ok = 0
        skipped = 0
        filtered = 0
        failed = 0

        print(f'\n===== 处理 {year} 年，股票数: {len(companies)} =====')
        for idx, item in enumerate(companies, start=1):
            ts_code = item.get('ts_code', '')
            symbol = _to_symbol(ts_code)
            out_file = os.path.join(year_dir, f'{symbol}.pkl')

            if not overwrite and os.path.exists(out_file):
                skipped += 1
                if checkpoint_every > 0 and idx % checkpoint_every == 0:
                    save_checkpoint(year, idx, len(companies), ok, skipped, filtered, failed, ts_code)
                continue

            unavailable_reason = _classify_item_availability(item, start_date, end_date)
            if unavailable_reason is None and _cache_starts_after_range(ds, symbol, end_date):
                unavailable_reason = 'not_listed_yet_by_cache'
            if unavailable_reason:
                filtered += 1
                _append_error(
                    error_file,
                    f'year={year} symbol={symbol} ts_code={ts_code} status=skipped reason={unavailable_reason}',
                )
                if checkpoint_every > 0 and idx % checkpoint_every == 0:
                    save_checkpoint(year, idx, len(companies), ok, skipped, filtered, failed, ts_code)
                continue

            try:
                if cache_only:
                    df = _load_from_fallback_cache(ds, symbol, start_date, end_date)
                else:
                    df = _fetch_with_retry(ds, symbol, start_date, end_date, retries=retries)
                if df is None or df.empty:
                    failed += 1
                    _append_error(
                        error_file,
                        (
                            f'year={year} symbol={symbol} ts_code={ts_code} '
                            f"status=failed reason={'cache_miss_or_empty' if cache_only else 'empty_or_retry_exhausted'}"
                        ),
                    )
                else:
                    df.to_pickle(out_file)
                    ok += 1
            except Exception as e:
                failed += 1
                _append_error(
                    error_file,
                    f'year={year} symbol={symbol} ts_code={ts_code} status=exception error={e}',
                )

            if checkpoint_every > 0 and idx % checkpoint_every == 0:
                save_checkpoint(year, idx, len(companies), ok, skipped, filtered, failed, ts_code)

            # 单请求随机停顿
            _sleep_random(min_request_sleep, max_request_sleep)

            # 批次停顿
            if idx % batch_size == 0:
                _sleep_random(min_batch_sleep, max_batch_sleep, f'批次 {idx // batch_size} 完成')

        summary['years'][str(year)] = {
            'total': len(companies),
            'ok': ok,
            'skipped': skipped,
            'filtered': filtered,
            'failed': failed,
            'path': os.path.abspath(year_dir),
            'date_range': {'start': start_date, 'end': end_date},
        }
        save_checkpoint(year, len(companies), len(companies), ok, skipped, filtered, failed, '')
        print(f'{year} 完成: ok={ok}, skipped={skipped}, filtered={filtered}, failed={failed}')

    summary_file = os.path.join(output_dir, 'prefetch_summary.json')
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f'\n全部完成，汇总文件: {os.path.abspath(summary_file)}')


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='按年份分批预取市场历史数据（随机停顿）')
    parser.add_argument(
        '--input',
        type=str,
        default='data/report/a_share_mcap_30_1000yi_2020_2026.json',
        help='年份分组证券清单 JSON 文件',
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/yearly_market_data',
        help='输出目录（按年份分子目录）',
    )
    parser.add_argument('--batch-size', type=int, default=20)
    parser.add_argument('--min-request-sleep', type=float, default=0.8)
    parser.add_argument('--max-request-sleep', type=float, default=2.2)
    parser.add_argument('--min-batch-sleep', type=float, default=8.0)
    parser.add_argument('--max-batch-sleep', type=float, default=18.0)
    parser.add_argument('--retries', type=int, default=3)
    parser.add_argument('--checkpoint-every', type=int, default=1, help='每处理多少只证券写一次 checkpoint')
    parser.add_argument('--overwrite', action='store_true', help='覆盖已存在文件')
    parser.add_argument('--cache-only', action='store_true', help='仅从统一缓存补写文件，不访问外部数据源')
    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    prefetch(
        input_json=args.input,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        min_request_sleep=args.min_request_sleep,
        max_request_sleep=args.max_request_sleep,
        min_batch_sleep=args.min_batch_sleep,
        max_batch_sleep=args.max_batch_sleep,
        retries=args.retries,
        overwrite=args.overwrite,
        checkpoint_every=args.checkpoint_every,
        cache_only=args.cache_only,
    )


if __name__ == '__main__':
    main()
