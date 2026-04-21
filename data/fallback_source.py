"""多数据源自动降级入口。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Iterable, List

import numpy as np
import pandas as pd

from .akshare_source import AkshareDataSource
from .sina_source import SinaDataSource
from .symbol_utils import is_probable_etf
from .tushare_source import TushareDataSource
from .yfinance_source import YFinanceDataSource


class FallbackDataSource:
    """按优先级依次尝试数据源，失败自动切换。"""

    REQUIRED_COLUMNS = ['open', 'high', 'low', 'close', 'volume']

    def __init__(self, priority: Iterable[str] | None = None, cache_dir: str | None = None):
        self.priority: List[str] = list(priority or ['tushare', 'sina', 'akshare', 'yfinance'])
        self.cache_dir = cache_dir or os.path.expanduser('~/.openclaw/workspace/backtest_cache')
        os.makedirs(self.cache_dir, exist_ok=True)
        self._registry = {
            'sina': SinaDataSource,
            'tushare': TushareDataSource,
            'akshare': AkshareDataSource,
            'yfinance': YFinanceDataSource,
        }

    def _priority_for_symbol(self, symbol: str) -> List[str]:
        if not is_probable_etf(symbol):
            return list(self.priority)

        preferred = ['yfinance']
        remaining = [name for name in self.priority if name not in preferred]
        return preferred + remaining

    def _normalize_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty:
            raise RuntimeError('返回空数据')
        if not isinstance(df.index, pd.DatetimeIndex):
            raise RuntimeError('索引不是 DatetimeIndex')

        missing = [column for column in self.REQUIRED_COLUMNS if column not in df.columns]
        if missing:
            raise RuntimeError(f'字段缺失: {missing}')

        work = df[self.REQUIRED_COLUMNS].copy()
        work.index = pd.to_datetime(work.index)
        work = work[~work.index.duplicated(keep='last')].sort_index()

        for column in self.REQUIRED_COLUMNS:
            work[column] = pd.to_numeric(work[column], errors='coerce')

        work = work.replace([np.inf, -np.inf], np.nan).dropna()
        if work.empty:
            raise RuntimeError('清洗后无有效数据')
        if (work['close'] <= 0).any():
            raise RuntimeError('close 存在非正数')
        if (work['volume'] < 0).any():
            raise RuntimeError('volume 存在负数')
        return work

    def _has_suspiciously_short_history(
        self,
        df: pd.DataFrame,
        start_date: str,
        end_date: str,
    ) -> bool:
        request_days = (datetime.strptime(end_date, '%Y%m%d') - datetime.strptime(start_date, '%Y%m%d')).days
        if request_days < 180:
            return False
        return len(df) < 60

    def _should_tolerate_gap_fetch_failure(self, gap_start: str, gap_end: str) -> bool:
        gap_days = (datetime.strptime(gap_end, '%Y%m%d') - datetime.strptime(gap_start, '%Y%m%d')).days + 1
        return gap_days <= 3

    def _has_sufficient_existing_history(self, df: pd.DataFrame) -> bool:
        return len(df) >= 60

    def _fetch_with_fallback(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        errors: List[str] = []
        for name in self._priority_for_symbol(symbol):
            source_cls = self._registry.get(name)
            if source_cls is None:
                errors.append(f'{name}: 未注册数据源')
                continue

            try:
                print(f'尝试数据源: {name}')
                source = source_cls()
                # 统一缓存层负责缓存，这里禁用下游缓存避免重复逻辑
                df = source.get_data(symbol, start_date, end_date, use_cache=False)
                df = self._normalize_frame(df)
                if self._has_suspiciously_short_history(df, start_date, end_date):
                    raise RuntimeError(f'历史数据过短: {len(df)} 条')
                print(f'数据源 {name} 获取成功')
                return df
            except Exception as e:
                msg = f'{name} 失败: {e}'
                errors.append(msg)
                print(msg)

        raise RuntimeError('所有数据源都获取失败: ' + ' | '.join(errors))

    def _slice(self, df: pd.DataFrame, start_date: str, end_date: str) -> pd.DataFrame:
        start = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
        end = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'
        return df.loc[start:end]

    def get_data(self, symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        if not use_cache:
            return self._fetch_with_fallback(symbol, start_date, end_date)

        req_start = datetime.strptime(start_date, '%Y%m%d')
        req_end = datetime.strptime(end_date, '%Y%m%d')
        cache_file = os.path.join(self.cache_dir, f'fallback_{symbol}.pkl')

        cached_df = None
        if os.path.exists(cache_file):
            try:
                cached_df = pd.read_pickle(cache_file).sort_index()
                print(f'使用统一缓存: {cache_file} ({len(cached_df)} 条)')
            except Exception as e:
                print(f'统一缓存读取失败: {e}')
                cached_df = None

        if cached_df is None or cached_df.empty:
            fresh = self._fetch_with_fallback(symbol, start_date, end_date)
            fresh = fresh[~fresh.index.duplicated(keep='last')].sort_index()
            fresh.to_pickle(cache_file)
            print(f'统一缓存写入: {cache_file} ({len(fresh)} 条)')
            return self._slice(fresh, start_date, end_date)

        merged = cached_df
        cache_start = merged.index.min()
        cache_end = merged.index.max()

        # 向前补齐（请求更早的时间）
        if req_start < cache_start:
            front_start = start_date
            front_end = (cache_start - timedelta(days=1)).strftime('%Y%m%d')
            try:
                front = self._fetch_with_fallback(symbol, front_start, front_end)
            except Exception as e:
                if self._should_tolerate_gap_fetch_failure(front_start, front_end):
                    print(f'统一缓存前向补齐跳过: {front_start} ~ {front_end}, 原因: {e}')
                    front = None
                elif self._has_sufficient_existing_history(merged):
                    print(f'统一缓存前向历史不足，保留现有缓存: {front_start} ~ {front_end}, 原因: {e}')
                    front = None
                else:
                    raise
            if front is not None and not front.empty:
                merged = pd.concat([front, merged])
                print(f'统一缓存前向补齐: {len(front)} 条 ({front_start} ~ {front_end})')

        # 向后补齐（请求更新的时间）
        if req_end > cache_end:
            back_start = (cache_end + timedelta(days=1)).strftime('%Y%m%d')
            back_end = end_date
            try:
                back = self._fetch_with_fallback(symbol, back_start, back_end)
            except Exception as e:
                if self._should_tolerate_gap_fetch_failure(back_start, back_end):
                    print(f'统一缓存后向补齐跳过: {back_start} ~ {back_end}, 原因: {e}')
                    back = None
                elif self._has_sufficient_existing_history(merged):
                    print(f'统一缓存后向历史不足，保留现有缓存: {back_start} ~ {back_end}, 原因: {e}')
                    back = None
                else:
                    raise
            if back is not None and not back.empty:
                merged = pd.concat([merged, back])
                print(f'统一缓存后向补齐: {len(back)} 条 ({back_start} ~ {back_end})')

        merged = merged[~merged.index.duplicated(keep='last')].sort_index()
        merged.to_pickle(cache_file)

        result = self._slice(merged, start_date, end_date)
        print(f'返回区间数据: {len(result)} 条')
        return result
