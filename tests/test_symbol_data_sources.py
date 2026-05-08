import unittest
import os
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace

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

    def test_should_use_environment_token_without_writing_tk_csv(self):
        calls = []

        class FakePro:
            def daily(self, ts_code, start_date, end_date):
                calls.append((ts_code, start_date, end_date))
                return pd.DataFrame(
                    {
                        "trade_date": ["20220104", "20220103"],
                        "open": [2.0, 1.0],
                        "high": [2.1, 1.1],
                        "low": [1.9, 0.9],
                        "close": [2.0, 1.0],
                        "vol": [200, 100],
                    }
                )

        fake_ts = SimpleNamespace(
            set_token=lambda token: (_ for _ in ()).throw(AssertionError("should not call set_token")),
            pro_api=lambda: FakePro(),
        )

        old_token = os.environ.get("TUSHARE_TOKEN")
        old_module = sys.modules.get("tushare")
        os.environ["TUSHARE_TOKEN"] = "env-token"
        sys.modules["tushare"] = fake_ts
        try:
            df = TushareDataSource().get_data("512480", "20220101", "20220131", use_cache=False)
        finally:
            if old_module is None:
                sys.modules.pop("tushare", None)
            else:
                sys.modules["tushare"] = old_module
            if old_token is None:
                os.environ.pop("TUSHARE_TOKEN", None)
            else:
                os.environ["TUSHARE_TOKEN"] = old_token

        self.assertEqual(calls, [("512480.SH", "20220101", "20220131")])
        self.assertEqual(list(df.index.strftime("%Y%m%d")), ["20220103", "20220104"])

    def test_should_prioritize_yfinance_for_etf_symbols(self):
        source = FallbackDataSource(priority=["tushare", "sina", "akshare", "yfinance"])
        self.assertEqual(
            source._priority_for_symbol("510300"),
            ["yfinance", "tushare", "sina", "akshare"],
        )

    def test_should_skip_yfinance_batch_for_non_etf_symbols(self):
        calls = []
        frame = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80, freq="B"),
        )

        class YFinanceOnlySource:
            def get_data_batch(self, symbols, start_date, end_date, use_cache=False):
                calls.append(("yfinance", list(symbols)))
                return {}

        class TushareBatchSource:
            def get_data_batch(self, symbols, start_date, end_date, use_cache=False):
                calls.append(("tushare", list(symbols)))
                return {symbol: frame for symbol in symbols}

        source = FallbackDataSource(priority=["yfinance", "tushare"])
        source._registry = {"yfinance": YFinanceOnlySource, "tushare": TushareBatchSource}

        frames = source.get_data_batch(["600519"], "20260101", "20260430", use_cache=False)

        self.assertEqual(set(frames.keys()), {"600519"})
        self.assertEqual(calls, [("tushare", ["600519"])])

    def test_should_keep_default_priority_for_stock_symbols(self):
        source = FallbackDataSource(priority=["tushare", "sina", "akshare", "yfinance"])
        self.assertEqual(
            source._priority_for_symbol("002149"),
            ["tushare", "sina", "akshare", "yfinance"],
        )

    def test_should_demote_source_after_five_consecutive_failures(self):
        calls = []
        frame = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2022-01-03", periods=80, freq="B"),
        )

        class FlakySource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                calls.append(("flaky", symbol))
                raise RuntimeError("temporary failure")

        class GoodSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                calls.append(("good", symbol))
                return frame

        source = FallbackDataSource(priority=["flaky", "good"])
        source._registry = {"flaky": FlakySource, "good": GoodSource}

        for idx in range(6):
            df = source.get_data(f"{idx:06d}", "20220101", "20221231", use_cache=False)
            self.assertEqual(len(df), 80)

        self.assertEqual(calls[:11], [
            ("flaky", "000000"), ("good", "000000"),
            ("flaky", "000001"), ("good", "000001"),
            ("flaky", "000002"), ("good", "000002"),
            ("flaky", "000003"), ("good", "000003"),
            ("flaky", "000004"), ("good", "000004"),
            ("good", "000005"),
        ])

    def test_should_reset_failure_streak_after_source_success(self):
        calls = []
        frame = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2022-01-03", periods=80, freq="B"),
        )
        attempts = {"flaky": 0}

        class FlakySource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                attempts["flaky"] += 1
                calls.append(("flaky", symbol, attempts["flaky"]))
                if attempts["flaky"] <= 5:
                    raise RuntimeError("temporary failure")
                return frame

        class GoodSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                if symbol == "000005":
                    calls.append(("good", symbol, "fail"))
                    raise RuntimeError("good failed")
                calls.append(("good", symbol))
                return frame

        source = FallbackDataSource(priority=["flaky", "good"])
        source._registry = {"flaky": FlakySource, "good": GoodSource}

        for idx in range(5):
            source.get_data(f"{idx:06d}", "20220101", "20221231", use_cache=False)

        calls.clear()
        source.get_data("000005", "20220101", "20221231", use_cache=False)
        self.assertEqual(calls, [("good", "000005", "fail"), ("flaky", "000005", 6)])

        calls.clear()
        source.get_data("000006", "20220101", "20221231", use_cache=False)

        self.assertEqual(calls, [("flaky", "000006", 7)])

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

    def test_should_use_cached_effective_range_without_front_fill_for_single_symbol(self):
        cached = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2022-01-04", periods=80, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_510300.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)

            def fail_fetch(symbol, start_date, end_date):
                raise RuntimeError("should not fetch")

            source._fetch_with_fallback = fail_fetch

            df = source.get_data("510300", "20220101", "20220430", use_cache=True)

        self.assertEqual(len(df), 80)
        self.assertEqual(df.index.min(), pd.Timestamp("2022-01-04"))

    def test_should_use_cached_effective_range_without_refetch_in_batch_mode(self):
        cached = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2022-01-04", periods=80, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_510300.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)

            class NeverBatch:
                def get_data_batch(self, symbols, start_date, end_date, use_cache=False):
                    raise AssertionError("should not call batch fetch")

            source._registry = {"never": NeverBatch}
            source.priority = ["never"]

            def fail_fetch(symbol, start_date, end_date):
                raise RuntimeError("should not fetch")

            source._fetch_with_fallback = fail_fetch

            frames = source.get_data_batch(["510300"], "20220101", "20220430", use_cache=True)

        self.assertEqual(set(frames.keys()), {"510300"})
        self.assertEqual(len(frames["510300"]), 80)
        self.assertEqual(frames["510300"].index.min(), pd.Timestamp("2022-01-04"))

    def test_should_use_batch_history_source_and_fallback_for_remaining_symbols(self):
        frame = pd.DataFrame(
            {
                "open": [1.0] * 80,
                "high": [1.1] * 80,
                "low": [0.9] * 80,
                "close": [1.0] * 80,
                "volume": [100] * 80,
            },
            index=pd.date_range("2026-01-01", periods=80, freq="B"),
        )

        class BatchOnlySource:
            def get_data_batch(self, symbols, start_date, end_date, use_cache=False):
                return {"510300": frame}

        class SingleFallbackSource:
            def get_data(self, symbol, start_date, end_date, use_cache=False):
                if symbol == "159915":
                    out = frame.copy()
                    out["open"] *= 2
                    out["high"] *= 2
                    out["low"] *= 2
                    out["close"] *= 2
                    out["volume"] *= 2
                    return out
                raise RuntimeError("unexpected symbol")

        source = FallbackDataSource(priority=["batch", "single"])
        source._registry = {"batch": BatchOnlySource, "single": SingleFallbackSource}

        frames = source.get_data_batch(["510300", "159915"], "20260101", "20260430", use_cache=False)

        self.assertEqual(set(frames.keys()), {"510300", "159915"})
        self.assertEqual(len(frames["510300"]), 80)
        self.assertEqual(float(frames["159915"].iloc[0]["close"]), 2.0)

    def test_should_prefer_cached_history_for_current_close_confirmed_day(self):
        cached = pd.DataFrame(
            {
                "open": [1.0] * 79,
                "high": [1.1] * 79,
                "low": [0.9] * 79,
                "close": [1.0] * 79,
                "volume": [100] * 79,
            },
            index=pd.date_range("2026-01-12", periods=79, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_510300.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)

            def fail_fetch(symbol, start_date, end_date):
                raise RuntimeError("should not fetch")

            source._fetch_with_fallback = fail_fetch

            df = source.get_data(
                "510300",
                "20260112",
                "20260430",
                use_cache=True,
                prefer_cache_for_current_day=True,
            )

        self.assertEqual(len(df), 79)

    def test_should_fetch_current_close_confirmed_day_when_today_is_missing_from_cache(self):
        cached = pd.DataFrame(
            {
                "open": [1.0] * 78,
                "high": [1.1] * 78,
                "low": [0.9] * 78,
                "close": [1.0] * 78,
                "volume": [100] * 78,
            },
            index=pd.date_range("2026-01-12", periods=78, freq="B"),
        )
        fetched = pd.DataFrame(
            {
                "open": [1.0] * 79,
                "high": [1.1] * 79,
                "low": [0.9] * 79,
                "close": [1.0] * 79,
                "volume": [100] * 79,
            },
            index=pd.date_range("2026-01-12", periods=79, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            cached.to_pickle(f"{tmpdir}/fallback_510300.pkl")
            source = FallbackDataSource(cache_dir=tmpdir)
            fetch_calls = []

            def fetch(symbol, start_date, end_date):
                fetch_calls.append((symbol, start_date, end_date))
                return fetched

            source._fetch_with_fallback = fetch

            df = source.get_data(
                "510300",
                "20260112",
                "20260430",
                use_cache=True,
                prefer_cache_for_current_day=True,
            )

        self.assertEqual(df.index.max(), pd.Timestamp("2026-04-30"))
        self.assertEqual(fetch_calls, [("510300", "20260430", "20260430")])

    def test_should_not_cache_rows_beyond_requested_end_date(self):
        requested_end = "20260429"
        fetched = pd.DataFrame(
            {
                "open": [1.0] * 85,
                "high": [1.1] * 85,
                "low": [0.9] * 85,
                "close": [1.0] * 85,
                "volume": [100] * 85,
            },
            index=pd.date_range("2026-01-01", periods=85, freq="B"),
        )

        with TemporaryDirectory() as tmpdir:
            source = FallbackDataSource(cache_dir=tmpdir)
            source._fetch_with_fallback = lambda symbol, start_date, end_date: fetched

            df = source.get_data("510300", "20260101", requested_end, use_cache=True)
            cached = pd.read_pickle(f"{tmpdir}/fallback_510300.pkl")

        self.assertEqual(df.index.max(), pd.Timestamp("2026-04-29"))
        self.assertEqual(cached.index.max(), pd.Timestamp("2026-04-29"))


if __name__ == "__main__":
    unittest.main()
