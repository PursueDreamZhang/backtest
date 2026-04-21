"""Tushare 数据源。"""

from __future__ import annotations

import os
import time

import pandas as pd


_LAST_DAILY_CALL_TS = 0.0


class TushareDataSource:
    """基于 Tushare Pro 的 A 股日线数据源。"""

    def _load_token_from_local_env(self) -> str:
        local_env = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'config',
            'local.env',
        )
        if not os.path.exists(local_env):
            return ''

        try:
            with open(local_env, 'r', encoding='utf-8') as f:
                for raw in f:
                    line = raw.strip()
                    if not line or line.startswith('#') or '=' not in line:
                        continue
                    key, value = line.split('=', 1)
                    if key.strip() == 'TUSHARE_TOKEN':
                        return value.strip().strip('"').strip("'")
        except Exception:
            return ''
        return ''

    def _resolve_token(self) -> str:
        # 1) 优先环境变量
        token = os.getenv('TUSHARE_TOKEN', '').strip()
        if token:
            return token

        # 2) 可选本地配置（不提交版本库）
        token = self._load_token_from_local_env()
        if token:
            return token

        raise RuntimeError('未找到 Tushare token（请设置 TUSHARE_TOKEN 或配置 backtest/config/local.env）')

    def _to_ts_code(self, symbol: str) -> str:
        if symbol.startswith('6'):
            return f'{symbol}.SH'
        return f'{symbol}.SZ'

    def get_data(self, symbol: str, start_date: str, end_date: str, use_cache: bool = True) -> pd.DataFrame:
        global _LAST_DAILY_CALL_TS

        token = self._resolve_token()

        try:
            import tushare as ts
        except Exception as e:
            raise RuntimeError(f'tushare 不可用: {e}') from e

        ts.set_token(token)
        pro = ts.pro_api()

        ts_code = self._to_ts_code(symbol)
        print(f'正在从 Tushare 获取股票 {symbol}({ts_code}) 数据...')

        wait = 1.3 - (time.time() - _LAST_DAILY_CALL_TS)
        if wait > 0:
            time.sleep(wait)

        try:
            df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
            _LAST_DAILY_CALL_TS = time.time()
        except Exception as e:
            msg = str(e)
            if '每分钟最多访问该接口50次' in msg:
                print(f'  daily 限频，等待 65s 后重试: {symbol}')
                time.sleep(65)
                df = pro.daily(ts_code=ts_code, start_date=start_date, end_date=end_date)
                _LAST_DAILY_CALL_TS = time.time()
            else:
                raise

        if df is None or df.empty:
            raise RuntimeError(f'Tushare 返回空数据: {symbol}')

        # Tushare daily 返回倒序，这里统一转成时间升序
        out = df[['trade_date', 'open', 'high', 'low', 'close', 'vol']].copy()
        out = out.rename(columns={'trade_date': 'datetime', 'vol': 'volume'})
        out['datetime'] = pd.to_datetime(out['datetime'], format='%Y%m%d')
        out = out.set_index('datetime').sort_index()
        for c in ['open', 'high', 'low', 'close', 'volume']:
            out[c] = pd.to_numeric(out[c], errors='coerce')
        out = out[['open', 'high', 'low', 'close', 'volume']].dropna()
        print(f'获取完成（Tushare），共 {len(out)} 条')
        return out
