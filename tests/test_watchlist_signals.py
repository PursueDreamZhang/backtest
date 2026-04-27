import unittest

import pandas as pd

from watchlist.indicators import enrich_daily_indicators, support_distance_pct, volume_progress
from watchlist.signals import evaluate_symbol


class WatchlistIndicatorTests(unittest.TestCase):
    def test_should_compute_ma_and_support_distance(self):
        frame = pd.DataFrame(
            {
                "open": [10.0] * 45,
                "high": [10.5] * 45,
                "low": [9.5] * 45,
                "close": [10.0] * 44 + [10.2],
                "volume": [1000] * 45,
            },
            index=pd.date_range("2026-01-01", periods=45),
        )

        enriched = enrich_daily_indicators(frame)

        self.assertAlmostEqual(enriched.iloc[-1]["ma40"], 10.005, places=3)
        self.assertAlmostEqual(support_distance_pct(10.2, 10.0), 2.0)

    def test_should_compute_volume_progress(self):
        self.assertAlmostEqual(volume_progress(current_volume=500, avg_volume=1000), 0.5)
        self.assertIsNone(volume_progress(current_volume=500, avg_volume=0))


class WatchlistSignalTests(unittest.TestCase):
    def _frame(self, closes, volumes=None):
        volumes = volumes or [1000] * len(closes)
        return pd.DataFrame(
            {
                "open": closes,
                "high": [price * 1.01 for price in closes],
                "low": [price * 0.99 for price in closes],
                "close": closes,
                "volume": volumes,
            },
            index=pd.date_range("2026-01-01", periods=len(closes)),
        )

    def test_should_trigger_close_confirmed_ma40_spring(self):
        closes = [10.0] * 45 + [11.0] * 15 + [10.2, 10.1, 10.05, 10.15, 10.35]
        volumes = [1000] * 60 + [700, 700, 700, 700, 700]

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertEqual(result.confidence, "confirmed")
        self.assertIn("MA40", result.setup)

    def test_should_mark_intraday_invalid_when_price_breaks_stop(self):
        closes = [10.0] * 80
        quote = {
            "price": 9.4,
            "open": 10.0,
            "previous_close": 10.0,
            "high": 10.1,
            "low": 9.4,
            "volume": 500,
            "fetched_at": "2026-04-27T10:30:00",
        }

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes),
            mode="intraday",
            realtime_quote=quote,
        )

        self.assertEqual(result.group, "盘中失效")
        self.assertEqual(result.confidence, "provisional")

    def test_should_trigger_double_bottom_when_second_low_holds_and_recovers_ma5(self):
        closes = (
            [10.0] * 20
            + [9.8, 9.6, 9.4, 9.2, 9.0, 9.2, 9.4, 9.6, 9.8, 10.0]
            + [10.0] * 20
            + [9.7, 9.5, 9.3, 9.15, 9.2, 9.35, 9.55, 9.75, 9.95, 10.1]
        )

        result = evaluate_symbol(
            symbol="300124",
            name="汇川技术",
            instrument_type="stock",
            frame=self._frame(closes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertIn("双底", result.setup)

    def test_should_trigger_launch_candle_after_range_compression(self):
        closes = [10.0 + (index % 2) * 0.1 for index in range(60)] + [10.8]
        volumes = [1000] * 60 + [1800]

        result = evaluate_symbol(
            symbol="002747",
            name="埃斯顿",
            instrument_type="stock",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertIn("启动阳线", result.setup)


if __name__ == "__main__":
    unittest.main()
