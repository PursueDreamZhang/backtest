"""多数据源自动降级入口。"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from typing import Iterable, List

import pandas as pd

from .akshare_source import AkshareDataSource
from .sina_source import SinaDataSource
from .tushare_source import TushareDataSource
from .yfinance_source import YFinanceDataSource


class FallbackDataSource:
    """按优先级依次尝试数据源，失败自动切换。"""

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

    def _fetch_with_fallback(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        errors: List[str] = []
        for name in self.priority:
            source_cls = self._registry.get(name)
            if source_cls is None:
                errors.append(f'{name}: 未注册数据源')
                continue

            try:
                print(f'尝试数据源: {name}')
                source = source_cls()
                # 统一缓存层负责缓存，这里禁用下游缓存避免重复逻辑
                df = source.get_data(symbol, start_date, end_date, use_cache=False)
                if df is None or df.empty:
                    raise RuntimeError('返回空数据')
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
            front = self._fetch_with_fallback(symbol, front_start, front_end)
            if front is not None and not front.empty:
                merged = pd.concat([front, merged])
                print(f'统一缓存前向补齐: {len(front)} 条 ({front_start} ~ {front_end})')

        # 向后补齐（请求更新的时间）
        if req_end > cache_end:
            back_start = (cache_end + timedelta(days=1)).strftime('%Y%m%d')
            back_end = end_date
            back = self._fetch_with_fallback(symbol, back_start, back_end)
            if back is not None and not back.empty:
                merged = pd.concat([merged, back])
                print(f'统一缓存后向补齐: {len(back)} 条 ({back_start} ~ {back_end})')

        merged = merged[~merged.index.duplicated(keep='last')].sort_index()
        merged.to_pickle(cache_file)

        result = self._slice(merged, start_date, end_date)
        print(f'返回区间数据: {len(result)} 条')
        return result
