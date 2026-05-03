"""Realtime quote data sources."""

from __future__ import annotations

from datetime import datetime, time
from typing import Iterable, List

import pandas as pd
import requests

from .symbol_utils import infer_cn_exchange, is_probable_etf


QUOTE_FIELDS = [
    'source',
    'symbol',
    'name',
    'price',
    'open',
    'previous_close',
    'high',
    'low',
    'volume',
    'amount',
    'change',
    'change_pct',
    'bid_price',
    'ask_price',
    'bid1_price',
    'bid1_volume',
    'ask1_price',
    'ask1_volume',
    'trade_time',
    'quote_date',
    'market_session',
    'is_stale',
    'volume_unit',
    'fetched_at',
]


def normalize_cn_symbol(symbol: str) -> str:
    normalized = str(symbol).strip().upper()
    if normalized.startswith(('SH', 'SZ')) and len(normalized) >= 8:
        normalized = normalized[2:]
    if '.' in normalized:
        normalized = normalized.split('.', 1)[0]
    return normalized


def _to_float(value):
    if value is None:
        return None
    text = str(value).strip()
    if not text or text in {'-', '--', 'None', 'nan'}:
        return None
    try:
        return float(text.replace(',', ''))
    except ValueError:
        return None


def _to_int(value):
    number = _to_float(value)
    if number is None:
        return None
    return int(number)


def _pick(row, names):
    for name in names:
        if name in row and pd.notna(row[name]):
            return row[name]
    return None


def _classify_market_session(clock_text: str | None) -> str | None:
    if not clock_text:
        return None
    try:
        clock = datetime.strptime(clock_text, '%H:%M:%S').time()
    except ValueError:
        return None

    if clock < time(9, 30):
        return 'pre_market'
    if clock <= time(11, 30):
        return 'continuous'
    if clock < time(13, 0):
        return 'midday_break'
    if clock <= time(15, 0):
        return 'continuous'
    return 'closed'


def _is_stale_quote(quote_date: str | None) -> bool | None:
    if not quote_date:
        return None
    return quote_date < datetime.now().date().isoformat()


class SinaRealtimeQuoteSource:
    """Realtime quote source backed by Sina Finance."""

    def _to_sina_symbol(self, symbol: str) -> str:
        normalized = normalize_cn_symbol(symbol)
        exchange = infer_cn_exchange(normalized)
        prefix = 'sh' if exchange == 'SH' else 'sz'
        return f'{prefix}{normalized}'

    def get_quote(self, symbol: str) -> dict:
        normalized_symbol = normalize_cn_symbol(symbol)
        sina_symbol = self._to_sina_symbol(normalized_symbol)
        url = f'https://hq.sinajs.cn/list={sina_symbol}'
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            timeout=10,
            headers={'Referer': 'https://finance.sina.com.cn'},
        )
        if response.status_code != 200:
            raise RuntimeError(f'新浪实时接口返回 {response.status_code}')
        response.encoding = 'gbk'
        return self._parse_response(normalized_symbol, response.text)

    def get_quotes(self, symbols: Iterable[str]) -> dict[str, dict]:
        normalized_symbols = [normalize_cn_symbol(symbol) for symbol in symbols]
        unique_symbols = list(dict.fromkeys(normalized_symbols))
        if not unique_symbols:
            return {}

        sina_symbols = ",".join(self._to_sina_symbol(symbol) for symbol in unique_symbols)
        url = f'https://hq.sinajs.cn/list={sina_symbols}'
        session = requests.Session()
        session.trust_env = False
        response = session.get(
            url,
            timeout=10,
            headers={'Referer': 'https://finance.sina.com.cn'},
        )
        if response.status_code != 200:
            raise RuntimeError(f'新浪实时接口返回 {response.status_code}')
        response.encoding = 'gbk'

        quotes: dict[str, dict] = {}
        payload_by_symbol = self._split_batch_payload(response.text)
        for symbol in unique_symbols:
            payload = payload_by_symbol.get(symbol)
            if payload is None:
                continue
            quotes[symbol] = self._parse_response(symbol, payload)
        return quotes

    def _split_batch_payload(self, payload: str) -> dict[str, str]:
        result: dict[str, str] = {}
        for raw_line in payload.splitlines():
            line = raw_line.strip()
            if not line or '="' not in line:
                continue
            prefix = 'var hq_str_'
            if not line.startswith(prefix):
                continue
            symbol_token = line[len(prefix) :].split('=', 1)[0].strip()
            if not symbol_token:
                continue
            result[normalize_cn_symbol(symbol_token)] = line
        return result

    def _parse_response(self, symbol: str, payload: str) -> dict:
        if '="' not in payload:
            raise RuntimeError('新浪实时接口响应格式异常')

        raw = payload.split('="', 1)[1].rsplit('"', 1)[0]
        fields = raw.split(',')
        if len(fields) < 32 or not fields[0]:
            raise RuntimeError(f'新浪实时接口返回空数据: {symbol}')

        price = _to_float(fields[3])
        previous_close = _to_float(fields[2])
        change = None
        change_pct = None
        if price is not None and previous_close not in (None, 0):
            change = price - previous_close
            change_pct = change / previous_close * 100

        trade_date = fields[30].strip() if len(fields) > 30 else ''
        trade_clock = fields[31].strip() if len(fields) > 31 else ''
        trade_time = f'{trade_date} {trade_clock}'.strip() if trade_date or trade_clock else None
        quote_date = trade_date or None

        return {
            'source': 'sina',
            'symbol': normalize_cn_symbol(symbol),
            'name': fields[0].strip(),
            'price': price,
            'open': _to_float(fields[1]),
            'previous_close': previous_close,
            'high': _to_float(fields[4]),
            'low': _to_float(fields[5]),
            'volume': _to_int(fields[8]),
            'amount': _to_float(fields[9]),
            'change': change,
            'change_pct': change_pct,
            'bid_price': _to_float(fields[6]),
            'ask_price': _to_float(fields[7]),
            'bid1_price': _to_float(fields[11]),
            'bid1_volume': _to_int(fields[10]),
            'ask1_price': _to_float(fields[21]),
            'ask1_volume': _to_int(fields[20]),
            'trade_time': trade_time,
            'quote_date': quote_date,
            'market_session': _classify_market_session(trade_clock),
            'is_stale': _is_stale_quote(quote_date),
            'volume_unit': 'share',
            'fetched_at': datetime.now().isoformat(timespec='seconds'),
        }


class AkshareRealtimeQuoteSource:
    """Realtime quote source backed by AkShare Eastmoney spot APIs."""

    def get_quote(self, symbol: str) -> dict:
        normalized_symbol = normalize_cn_symbol(symbol)
        try:
            import akshare as ak
        except Exception as e:
            raise RuntimeError(f'akshare 不可用: {e}') from e

        if is_probable_etf(normalized_symbol):
            frame = ak.fund_etf_spot_em()
        else:
            frame = ak.stock_zh_a_spot_em()
        return self._parse_spot_frame(normalized_symbol, frame)

    def get_quotes(self, symbols: Iterable[str]) -> dict[str, dict]:
        normalized_symbols = [normalize_cn_symbol(symbol) for symbol in symbols]
        result: dict[str, dict] = {}
        etf_symbols = [symbol for symbol in normalized_symbols if is_probable_etf(symbol)]
        stock_symbols = [symbol for symbol in normalized_symbols if not is_probable_etf(symbol)]

        try:
            import akshare as ak
        except Exception as e:
            raise RuntimeError(f'akshare 不可用: {e}') from e

        if etf_symbols:
            frame = ak.fund_etf_spot_em()
            for symbol in etf_symbols:
                result[symbol] = self._parse_spot_frame(symbol, frame)
        if stock_symbols:
            frame = ak.stock_zh_a_spot_em()
            for symbol in stock_symbols:
                result[symbol] = self._parse_spot_frame(symbol, frame)
        return result

    def _parse_spot_frame(self, symbol: str, frame: pd.DataFrame) -> dict:
        normalized_symbol = normalize_cn_symbol(symbol)
        if frame is None or frame.empty:
            raise RuntimeError(f'AkShare 实时接口返回空数据: {symbol}')
        if '代码' not in frame.columns:
            raise RuntimeError('AkShare 实时接口字段缺失: 代码')

        work = frame.copy()
        work['代码'] = work['代码'].astype(str).str.strip()
        matched = work[work['代码'] == normalized_symbol]
        if matched.empty:
            raise RuntimeError(f'AkShare 实时接口未找到标的: {symbol}')

        row = matched.iloc[0]
        price = _to_float(_pick(row, ['最新价', '最新']))
        previous_close = _to_float(_pick(row, ['昨收', '昨收价']))
        change = _to_float(_pick(row, ['涨跌额']))
        change_pct = _to_float(_pick(row, ['涨跌幅']))

        if change is None and price is not None and previous_close is not None:
            change = price - previous_close
        if change_pct is None and change is not None and previous_close not in (None, 0):
            change_pct = change / previous_close * 100

        volume = _to_int(_pick(row, ['成交量']))
        if volume is not None:
            volume *= 100

        return {
            'source': 'akshare',
            'symbol': normalized_symbol,
            'name': str(_pick(row, ['名称']) or '').strip(),
            'price': price,
            'open': _to_float(_pick(row, ['今开', '开盘', '开盘价'])),
            'previous_close': previous_close,
            'high': _to_float(_pick(row, ['最高', '最高价'])),
            'low': _to_float(_pick(row, ['最低', '最低价'])),
            'volume': volume,
            'amount': _to_float(_pick(row, ['成交额'])),
            'change': change,
            'change_pct': change_pct,
            'bid_price': None,
            'ask_price': None,
            'bid1_price': None,
            'bid1_volume': None,
            'ask1_price': None,
            'ask1_volume': None,
            'trade_time': None,
            'quote_date': None,
            'market_session': None,
            'is_stale': None,
            'volume_unit': 'share',
            'fetched_at': datetime.now().isoformat(timespec='seconds'),
        }


class RealtimeQuoteSource:
    """Realtime quote source with Sina as default and AkShare as fallback."""

    def __init__(self, priority: Iterable[str] | None = None):
        self.priority: List[str] = list(priority or ['sina', 'akshare'])
        self._registry = {
            'sina': SinaRealtimeQuoteSource,
            'akshare': AkshareRealtimeQuoteSource,
        }

    def get_quote(self, symbol: str) -> dict:
        normalized_symbol = normalize_cn_symbol(symbol)
        errors: List[str] = []
        for name in self.priority:
            source_cls = self._registry.get(name)
            if source_cls is None:
                errors.append(f'{name}: 未注册实时数据源')
                continue

            try:
                quote = source_cls().get_quote(normalized_symbol)
                return self._normalize_quote(quote)
            except Exception as e:
                errors.append(f'{name} 失败: {e}')

        raise RuntimeError('所有实时数据源都获取失败: ' + ' | '.join(errors))

    def get_quotes(self, symbols: Iterable[str]) -> list[dict]:
        normalized_symbols = [normalize_cn_symbol(symbol) for symbol in symbols]
        quotes_by_symbol: dict[str, dict] = {}
        remaining = list(dict.fromkeys(normalized_symbols))
        errors: List[str] = []

        for name in self.priority:
            if not remaining:
                break

            source_cls = self._registry.get(name)
            if source_cls is None:
                errors.append(f'{name}: 未注册实时数据源')
                continue

            source = source_cls()
            try:
                raw_quotes = self._get_quotes_from_source(source, remaining)
            except Exception as e:
                errors.append(f'{name} 批量失败: {e}')
                continue

            next_remaining: list[str] = []
            for symbol in remaining:
                raw_quote = raw_quotes.get(symbol)
                if raw_quote is None:
                    next_remaining.append(symbol)
                    continue
                try:
                    quotes_by_symbol[symbol] = self._normalize_quote(raw_quote)
                except Exception as e:
                    errors.append(f'{name} {symbol} 失败: {e}')
                    next_remaining.append(symbol)
            remaining = next_remaining

        if remaining:
            raise RuntimeError('部分实时行情获取失败: ' + ', '.join(remaining) + ' | ' + ' | '.join(errors))

        return [quotes_by_symbol[symbol] for symbol in normalized_symbols]

    def _get_quotes_from_source(self, source, symbols: list[str]) -> dict[str, dict]:
        if hasattr(source, 'get_quotes'):
            return source.get_quotes(symbols)
        return {symbol: source.get_quote(symbol) for symbol in symbols}

    def _normalize_quote(self, quote: dict) -> dict:
        normalized = {field: quote.get(field) for field in QUOTE_FIELDS}
        normalized['symbol'] = normalize_cn_symbol(normalized['symbol'])
        if not normalized['symbol']:
            raise RuntimeError('实时行情缺少 symbol')
        if normalized['price'] is None:
            raise RuntimeError(f'实时行情缺少最新价: {normalized["symbol"]}')
        if normalized['change'] is None and normalized['previous_close'] not in (None, 0):
            normalized['change'] = normalized['price'] - normalized['previous_close']
        if normalized['change_pct'] is None and normalized['change'] is not None and normalized['previous_close'] not in (None, 0):
            normalized['change_pct'] = normalized['change'] / normalized['previous_close'] * 100
        if normalized['volume_unit'] is None:
            normalized['volume_unit'] = 'share'
        if normalized['is_stale'] is None:
            normalized['is_stale'] = _is_stale_quote(normalized['quote_date'])
        return normalized

    def validate_for_intraday_strategy(self, quote: dict) -> None:
        missing = [
            field
            for field in ['price', 'open', 'previous_close', 'high', 'low', 'volume']
            if quote.get(field) is None
        ]
        if missing:
            raise RuntimeError(f'实时行情缺少盘中策略字段: {missing}')
        if quote.get('is_stale') is True:
            raise RuntimeError(f'实时行情已过期: {quote.get("symbol")}')
