"""AkShare 数据源。"""

from __future__ import annotations

import pandas as pd


class AkshareDataSource:
    """基于 AkShare 的 A 股日线数据源。"""

    def get_data(self, symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        try:
            import akshare as ak
        except Exception as e:
            raise RuntimeError(f'akshare 不可用: {e}') from e

        print(f'正在从 AkShare 获取股票 {symbol} 数据...')
        df = ak.stock_zh_a_hist(
            symbol=symbol,
            period='daily',
            start_date=start_date,
            end_date=end_date,
            adjust='',
        )
        if df is None or df.empty:
            raise RuntimeError(f'AkShare 返回空数据: {symbol}')

        # 适配常见中文列
        col_map = {
            '日期': 'datetime',
            '开盘': 'open',
            '收盘': 'close',
            '最高': 'high',
            '最低': 'low',
            '成交量': 'volume',
        }
        missing = [k for k in col_map if k not in df.columns]
        if missing:
            raise RuntimeError(f'AkShare 字段缺失: {missing}')

        out = df[list(col_map.keys())].rename(columns=col_map)
        out['datetime'] = pd.to_datetime(out['datetime'])
        out = out.set_index('datetime')
        for c in ['open', 'high', 'low', 'close', 'volume']:
            out[c] = pd.to_numeric(out[c], errors='coerce')
        out = out[['open', 'high', 'low', 'close', 'volume']].dropna()
        print(f'获取完成（AkShare），共 {len(out)} 条')
        return out
