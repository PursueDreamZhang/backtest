"""Yahoo Finance 数据源。"""

from __future__ import annotations

import pandas as pd


class YFinanceDataSource:
    """基于 yfinance 的 A 股日线数据源。"""

    def _to_ticker(self, symbol: str) -> str:
        if symbol.startswith('6'):
            return f'{symbol}.SS'
        return f'{symbol}.SZ'

    def get_data(self, symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        # 延迟导入，避免未安装时影响主流程
        try:
            import yfinance as yf
        except Exception as e:
            raise RuntimeError(f'yfinance 不可用: {e}') from e

        ticker = self._to_ticker(symbol)
        start = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
        end = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'

        print(f'正在从 yfinance 获取股票 {symbol}({ticker}) 数据...')
        df = yf.download(ticker, start=start, end=end, progress=False, auto_adjust=False)
        if df is None or df.empty:
            raise RuntimeError(f'yfinance 返回空数据: {symbol}')

        # 兼容不同 yfinance 版本列名格式（普通列 / MultiIndex tuple）
        def _norm_col(c):
            if isinstance(c, tuple):
                return str(c[0]).lower()
            return str(c).lower()

        cols = {_norm_col(c): c for c in df.columns}
        required = ['open', 'high', 'low', 'close', 'volume']
        missing = [c for c in required if c not in cols]
        if missing:
            raise RuntimeError(f'yfinance 字段缺失: {missing}')

        out = df[[cols['open'], cols['high'], cols['low'], cols['close'], cols['volume']]].copy()
        out.columns = ['open', 'high', 'low', 'close', 'volume']
        out.index = pd.to_datetime(out.index)
        out = out.dropna()
        print(f'获取完成（yfinance），共 {len(out)} 条')
        return out
