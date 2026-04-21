import unittest
from tempfile import TemporaryDirectory

import pandas as pd

from data.fallback_source import FallbackDataSource
from data.tushare_source import TushareDataSource
from data.yfinance_source import YFinanceDataSource


class SymbolSourceMappingTests(unittest.TestCase):
    def test_should_map_shanghai_etf_to_yfinance_ss_suffix(self):
        self.assertEqual(YFinanceDataSource()._to_ticker("510300"), "510300.SS")

    def test_should_map_shenzhen_etf_to_yfinance_sz_suffix(self):
        self.assertEqual(YFinanceDataSource()._to_ticker("159915"), "159915.SZ")

    def test_should_map_shanghai_etf_to_tushare_sh_suffix(self):
        self.assertEqual(TushareDataSource()._to_ts_code("512480"), "512480.SH")

    def test_should_prioritize_yfinance_for_etf_symbols(self):
        source = FallbackDataSource(priority=["tushare", "sina", "akshare", "yfinance"])
        self.assertEqual(
            source._priority_for_symbol("510300"),
            ["yfinance", "tushare", "sina", "akshare"],
        )

    def test_should_keep_default_priority_for_stock_symbols(self):
        source = FallbackDataSource(priority=["tushare", "sina", "akshare", "yfinance"])
        self.assertEqual(
            source._priority_for_symbol("002149"),
            ["tushare", "sina", "akshare", "yfinance"],
        )

    def test_should_continue_fallback_when_frame_is_missing_required_columns(self):
        class BadSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                return pd.DataFrame(
                    {"close": [1.0, 2.0]},
                    index=pd.to_datetime(["2022-01-03", "2022-01-04"]),
                )

        class GoodSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                return pd.DataFrame(
                    {
                        "open": [1.0, 2.0],
                        "high": [1.1, 2.1],
                        "low": [0.9, 1.9],
                        "close": [1.0, 2.0],
                        "volume": [100, 200],
                    },
                    index=pd.to_datetime(["2022-01-03", "2022-01-04"]),
                )

        source = FallbackDataSource(priority=["bad", "good"])
        source._registry = {"bad": BadSource, "good": GoodSource}

        df = source.get_data("510300", "20220101", "20220131", use_cache=False)

        self.assertEqual(list(df.columns), ["open", "high", "low", "close", "volume"])
        self.assertEqual(len(df), 2)

    def test_should_continue_fallback_when_history_is_suspiciously_short(self):
        class ShortSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                return pd.DataFrame(
                    {
                        "open": [1.0] * 10,
                        "high": [1.1] * 10,
                        "low": [0.9] * 10,
                        "close": [1.0] * 10,
                        "volume": [100] * 10,
                    },
                    index=pd.date_range("2022-01-03", periods=10, freq="B"),
                )

        class GoodSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                return pd.DataFrame(
                    {
                        "open": [1.0] * 80,
                        "high": [1.1] * 80,
                        "low": [0.9] * 80,
                        "close": [1.0] * 80,
                        "volume": [100] * 80,
                    },
                    index=pd.date_range("2022-01-03", periods=80, freq="B"),
                )

        source = FallbackDataSource(priority=["short", "good"])
        source._registry = {"short": ShortSource, "good": GoodSource}

        df = source.get_data("510300", "20220101", "20221231", use_cache=False)

        self.assertEqual(len(df), 80)

    def test_should_keep_cached_data_when_small_front_gap_fetch_fails(self):
        cached = pd.DataFrame(
            {
                "open": [1.0, 2.0],
                "high": [1.1, 2.1],
                "low": [0.9, 1.9],
                "close": [1.0, 2.0],
                "volume": [100, 200],
            },
            index=pd.to_datetime(["2022-01-04", "2022-01-05"]),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_510300.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)

            def fail_fetch(symbol, start_date, end_date):
                raise RuntimeError("network down")

            source._fetch_with_fallback = fail_fetch

            df = source.get_data("510300", "20220101", "20220105", use_cache=True)

        self.assertEqual(len(df), 2)
        self.assertEqual(df.index.min(), pd.Timestamp("2022-01-04"))

    def test_should_keep_cached_data_when_existing_history_is_sufficient(self):
        cached = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2025-10-09", periods=80, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_512100.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)

            def fail_fetch(symbol, start_date, end_date):
                raise RuntimeError("history unavailable")

            source._fetch_with_fallback = fail_fetch

            df = source.get_data("512100", "20220101", "20260421", use_cache=True)

        self.assertEqual(len(df), 80)
        self.assertEqual(df.index.min(), pd.Timestamp("2025-10-09"))


if __name__ == "__main__":
    unittest.main()
