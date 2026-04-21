"""
新浪数据源
从新浪财经获取A股历史数据
"""

import os

import pandas as pd
import requests
import json
from datetime import datetime, timedelta


class SinaDataSource:
    """新浪数据源"""
    
    def __init__(self, cache_dir=None):
        """
        初始化
        
        Args:
            cache_dir: 缓存目录，默认 ~/.openclaw/workspace/backtest_cache
        """
        self.cache_dir = cache_dir or os.path.expanduser('~/.openclaw/workspace/backtest_cache')

    def _ensure_cache_dir(self):
        os.makedirs(self.cache_dir, exist_ok=True)
    
    def get_data(self, symbol, start_date, end_date, use_cache=True):
        """
        获取股票数据
        
        Args:
            symbol: 股票代码
            start_date: 开始日期，如 '20200101'
            end_date: 结束日期，如 '20241231'
            use_cache: 是否使用缓存
        
        Returns:
            pandas DataFrame
        """
        req_start = datetime.strptime(start_date, '%Y%m%d')
        req_end = datetime.strptime(end_date, '%Y%m%d')

        # 按股票缓存，支持不同日期区间复用和增量更新
        cache_file = os.path.join(self.cache_dir, f'{symbol}.pkl')

        if not use_cache:
            return self._fetch_from_sina(symbol, start_date, end_date)

        self._ensure_cache_dir()

        cached_df = None
        if os.path.exists(cache_file):
            print(f'使用本地缓存: {cache_file}')
            try:
                cached_df = pd.read_pickle(cache_file)
                cached_df = cached_df.sort_index()
                print(f'缓存数据: {len(cached_df)} 条')
            except Exception as e:
                print(f'缓存读取失败: {e}')
                cached_df = None

        # 无缓存：直接拉取并落盘
        if cached_df is None or cached_df.empty:
            df = self._fetch_from_sina(symbol, start_date, end_date)
            if len(df) > 0:
                df.to_pickle(cache_file)
                print(f'获取完成（新浪），共 {len(df)} 条，已缓存')
            return df

        cache_start = cached_df.index.min()
        cache_end = cached_df.index.max()
        merged = cached_df

        # 前向缺口：请求开始日早于缓存开始日
        if req_start < cache_start:
            front_start = start_date
            front_end = (cache_start - timedelta(days=1)).strftime('%Y%m%d')
            front_df = self._fetch_from_sina(symbol, front_start, front_end)
            if front_df is not None and not front_df.empty:
                merged = pd.concat([front_df, merged])
                print(f'前向增量补齐: {len(front_df)} 条 ({front_start} ~ {front_end})')

        # 后向缺口：请求结束日晚于缓存结束日
        if req_end > cache_end:
            back_start = (cache_end + timedelta(days=1)).strftime('%Y%m%d')
            back_end = end_date
            back_df = self._fetch_from_sina(symbol, back_start, back_end)
            if back_df is not None and not back_df.empty:
                merged = pd.concat([merged, back_df])
                print(f'后向增量补齐: {len(back_df)} 条 ({back_start} ~ {back_end})')

        # 去重排序并回写缓存
        merged = merged[~merged.index.duplicated(keep='last')].sort_index()
        merged.to_pickle(cache_file)

        # 截取请求区间返回
        result = merged.loc[start_date[:4] + '-' + start_date[4:6] + '-' + start_date[6:]:
                            end_date[:4] + '-' + end_date[4:6] + '-' + end_date[6:]]
        print(f'返回区间数据: {len(result)} 条')
        return result
    
    def _fetch_from_sina(self, symbol, start_date, end_date):
        """从新浪接口获取数据"""
        # 股票代码转换
        if symbol.startswith('6'):
            sina_symbol = f'sh{symbol}'
        else:
            sina_symbol = f'sz{symbol}'
        
        # 计算需要的天数（新浪接口最大支持约1500天）
        start_dt = datetime.strptime(start_date, '%Y%m%d')
        end_dt = datetime.strptime(end_date, '%Y%m%d')
        days = min((end_dt - start_dt).days + 100, 1500)
        
        print(f'正在从新浪获取股票 {symbol} 数据...')
        
        session = requests.Session()
        session.trust_env = False
        
        url = f'https://quotes.sina.cn/cn/api/json_v2.php/CN_MarketDataService.getKLineData?symbol={sina_symbol}&scale=240&datalen={days}'
        
        r = session.get(url, timeout=30)
        
        if r.status_code != 200:
            raise Exception(f'新浪接口返回 {r.status_code}')
        
        data = json.loads(r.text)
        
        if not data:
            raise Exception('新浪接口返回空数据')
        
        # 转换为 DataFrame
        df = pd.DataFrame(data)
        df = df.rename(columns={
            'day': 'datetime',
            'open': 'open',
            'high': 'high',
            'low': 'low',
            'close': 'close',
            'volume': 'volume'
        })
        
        df['datetime'] = pd.to_datetime(df['datetime'])
        df = df.set_index('datetime')
        
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 过滤日期范围
        actual_start = df.index.min()
        actual_end = df.index.max()
        filter_start = max(start_dt, actual_start)
        filter_end = min(end_dt, actual_end)
        
        if filter_start <= filter_end:
            df = df.loc[filter_start:filter_end]
        
        print(f'实际数据范围: {actual_start.strftime("%Y-%m-%d")} ~ {actual_end.strftime("%Y-%m-%d")}')
        
        return df[['open', 'high', 'low', 'close', 'volume']]
