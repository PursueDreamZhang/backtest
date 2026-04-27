import unittest

import pandas as pd

from data.realtime_quote_source import (
    AkshareRealtimeQuoteSource,
    RealtimeQuoteSource,
    SinaRealtimeQuoteSource,
)


class RealtimeQuoteSourceTests(unittest.TestCase):
    def test_should_parse_sina_realtime_quote(self):
        source = SinaRealtimeQuoteSource()
        payload = (
            'var hq_str_sh510300="300ETF,3.928,3.900,3.950,3.970,3.910,'
            '3.949,3.950,12345600,48765432.10,100,3.949,200,3.948,'
            '300,3.947,400,3.946,500,3.945,600,3.950,700,3.951,'
            '800,3.952,900,3.953,1000,3.954,2026-04-27,14:55:03,00,";'
        )

        quote = source._parse_response("510300", payload)

        self.assertEqual(quote["source"], "sina")
        self.assertEqual(quote["symbol"], "510300")
        self.assertEqual(quote["name"], "300ETF")
        self.assertEqual(quote["trade_time"], "2026-04-27 14:55:03")
        self.assertEqual(quote["quote_date"], "2026-04-27")
        self.assertEqual(quote["market_session"], "continuous")
        self.assertFalse(quote["is_stale"])
        self.assertEqual(quote["volume_unit"], "share")
        self.assertEqual(quote["price"], 3.95)
        self.assertEqual(quote["open"], 3.928)
        self.assertEqual(quote["previous_close"], 3.9)
        self.assertEqual(quote["bid1_price"], 3.949)
        self.assertEqual(quote["ask1_price"], 3.95)
        self.assertEqual(quote["volume"], 12345600)
        self.assertEqual(quote["amount"], 48765432.10)

    def test_should_parse_akshare_realtime_quote_row(self):
        frame = pd.DataFrame(
            [
                {
                    "代码": "510300",
                    "名称": "沪深300ETF",
                    "最新价": 3.95,
                    "今开": 3.928,
                    "昨收": 3.9,
                    "最高": 3.97,
                    "最低": 3.91,
                    "成交量": 123456,
                    "成交额": 48765432.10,
                    "涨跌额": 0.05,
                    "涨跌幅": 1.28,
                }
            ]
        )

        source = AkshareRealtimeQuoteSource()
        quote = source._parse_spot_frame("510300", frame)

        self.assertEqual(quote["source"], "akshare")
        self.assertEqual(quote["symbol"], "510300")
        self.assertEqual(quote["name"], "沪深300ETF")
        self.assertEqual(quote["price"], 3.95)
        self.assertEqual(quote["open"], 3.928)
        self.assertEqual(quote["previous_close"], 3.9)
        self.assertEqual(quote["volume"], 12345600)
        self.assertEqual(quote["volume_unit"], "share")
        self.assertEqual(quote["change"], 0.05)
        self.assertEqual(quote["change_pct"], 1.28)

    def test_should_normalize_symbol_with_exchange_suffix(self):
        source = SinaRealtimeQuoteSource()
        self.assertEqual(source._to_sina_symbol("510300.SH"), "sh510300")
        self.assertEqual(source._to_sina_symbol("SZ159915"), "sz159915")

    def test_should_fallback_to_akshare_when_sina_fails(self):
        class BadSina:
            def get_quote(self, symbol):
                raise RuntimeError("sina down")

        class GoodAkshare:
            def get_quote(self, symbol):
                return {
                    "source": "akshare",
                    "symbol": symbol,
                    "name": "沪深300ETF",
                    "price": 3.95,
                }

        source = RealtimeQuoteSource()
        source._registry = {"sina": BadSina, "akshare": GoodAkshare}

        quote = source.get_quote("510300")

        self.assertEqual(quote["source"], "akshare")
        self.assertEqual(quote["symbol"], "510300")

    def test_should_continue_fallback_when_quote_normalization_fails(self):
        class BadSina:
            def get_quote(self, symbol):
                return {
                    "source": "sina",
                    "symbol": symbol,
                    "name": "坏数据",
                    "price": None,
                }

        class GoodAkshare:
            def get_quote(self, symbol):
                return {
                    "source": "akshare",
                    "symbol": symbol,
                    "name": "沪深300ETF",
                    "price": 3.95,
                    "previous_close": 3.9,
                }

        source = RealtimeQuoteSource()
        source._registry = {"sina": BadSina, "akshare": GoodAkshare}

        quote = source.get_quote("510300.SH")

        self.assertEqual(quote["source"], "akshare")
        self.assertEqual(quote["symbol"], "510300")

    def test_should_get_quotes_in_batch_and_preserve_input_order(self):
        class BatchSina:
            def __init__(self):
                self.calls = []

            def get_quotes(self, symbols):
                self.calls.append(list(symbols))
                return {
                    symbol: {
                        "source": "sina",
                        "symbol": symbol,
                        "name": symbol,
                        "price": index + 1.0,
                        "previous_close": index + 0.9,
                    }
                    for index, symbol in enumerate(symbols)
                    if symbol != "000001"
                }

        class SingleAkshare:
            def get_quote(self, symbol):
                return {
                    "source": "akshare",
                    "symbol": symbol,
                    "name": symbol,
                    "price": 10.0,
                    "previous_close": 9.8,
                }

        source = RealtimeQuoteSource()
        batch_sina = BatchSina()
        source._registry = {"sina": lambda: batch_sina, "akshare": SingleAkshare}

        quotes = source.get_quotes(["510300.SH", "000001.SZ"])

        self.assertEqual([quote["symbol"] for quote in quotes], ["510300", "000001"])
        self.assertEqual([quote["source"] for quote in quotes], ["sina", "akshare"])
        self.assertEqual(batch_sina.calls, [["510300", "000001"]])


if __name__ == "__main__":
    unittest.main()
