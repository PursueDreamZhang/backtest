"""Yahoo Finance 数据源。"""

from __future__ import annotations

import pandas as pd

from .symbol_utils import infer_cn_exchange


class YFinanceDataSource:
    """基于 yfinance 的 A 股日线数据源。"""

    def _to_ticker(self, symbol: str) -> str:
        exchange = infer_cn_exchange(symbol)
        if exchange == 'SH':
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

    def get_data_batch(self, symbols: list[str], start_date: str, end_date: str, use_cache: bool = True) -> dict[str, pd.DataFrame]:
        try:
            import yfinance as yf
        except Exception as e:
            raise RuntimeError(f'yfinance 不可用: {e}') from e

        unique_symbols = list(dict.fromkeys(symbols))
        if not unique_symbols:
            return {}

        ticker_to_symbol = {self._to_ticker(symbol): symbol for symbol in unique_symbols}
        tickers = list(ticker_to_symbol.keys())
        start = f'{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}'
        end = f'{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}'

        print(f'正在从 yfinance 批量获取 {len(unique_symbols)} 个标的数据...')
        df = yf.download(tickers, start=start, end=end, progress=False, auto_adjust=False, group_by="ticker")
        if df is None or df.empty:
            raise RuntimeError('yfinance 批量返回空数据')

        results: dict[str, pd.DataFrame] = {}
        if not isinstance(df.columns, pd.MultiIndex):
            symbol = unique_symbols[0]
            part = df.copy()
            part.columns = [str(column).lower() for column in part.columns]
            required = ['open', 'high', 'low', 'close', 'volume']
            missing = [column for column in required if column not in part.columns]
            if missing:
                return {}
            out = part[required].copy()
            out.index = pd.to_datetime(out.index)
            out = out.dropna()
            if not out.empty:
                results[symbol] = out
            print(f'获取完成（yfinance 批量），成功 {len(results)} 个')
            return results

        for ticker, symbol in ticker_to_symbol.items():
            if ticker not in df.columns.get_level_values(0):
                continue
            part = df[ticker].copy()
            part.columns = [str(column).lower() for column in part.columns]
            required = ['open', 'high', 'low', 'close', 'volume']
            missing = [column for column in required if column not in part.columns]
            if missing:
                continue
            out = part[required].copy()
            out.index = pd.to_datetime(out.index)
            out = out.dropna()
            if not out.empty:
                results[symbol] = out
        print(f'获取完成（yfinance 批量），成功 {len(results)} 个')
        return results
