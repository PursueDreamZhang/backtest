import unittest

import pandas as pd

from watchlist.indicators import enrich_daily_indicators, support_distance_pct, volume_progress
from watchlist.signals import _double_bottom_candidate, evaluate_symbol


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
    def _frame(self, closes, volumes=None, highs=None, lows=None):
        volumes = volumes or [1000] * len(closes)
        highs = highs or [price * 1.01 for price in closes]
        lows = lows or [price * 0.99 for price in closes]
        return pd.DataFrame(
            {
                "open": closes,
                "high": highs,
                "low": lows,
                "close": closes,
                "volume": volumes,
            },
            index=pd.date_range("2026-01-01", periods=len(closes)),
        )

    def test_should_trigger_close_confirmed_ma40_spring(self):
        closes = [10 + 0.1 * index for index in range(55)] + [15.0, 14.7, 14.45, 14.25, 14.1, 14.12, 14.18, 14.24, 13.8, 14.55]
        highs = []
        lows = []
        for index, price in enumerate(closes):
            if index >= len(closes) - 5:
                highs.append(price * 1.005)
                lows.append(price * 0.995)
            else:
                highs.append(price * 1.015)
                lows.append(price * 0.985)
        volumes = [1500] * 55 + [900, 850, 820, 780, 740, 700, 710, 720, 730, 760]

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes, volumes, highs, lows),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertEqual(result.confidence, "confirmed")
        self.assertIn("MA40", result.setup)

    def test_should_not_trigger_ma40_spring_in_downtrend(self):
        closes = [18 - 0.1 * index for index in range(55)] + [12.8, 12.6, 12.5, 12.35, 12.2, 12.18, 12.12, 12.16, 12.22, 12.3]
        volumes = [1500] * 55 + [900, 860, 840, 820, 800, 790, 780, 770, 760, 750]

        result = evaluate_symbol(
            symbol="510300",
            name="测试ETF",
            instrument_type="etf",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertNotEqual(result.setup, "MA40 弹簧压紧后松开")
        self.assertNotEqual(result.group, "触发买点")

    def test_should_require_gain_above_five_percent_for_ma40_spring_trigger(self):
        closes = [10 + 0.1 * index for index in range(55)] + [15.0, 14.7, 14.45, 14.25, 14.1, 14.12, 14.18, 14.24, 14.36, 14.5]
        highs = []
        lows = []
        for index, price in enumerate(closes):
            if index >= len(closes) - 5:
                highs.append(price * 1.005)
                lows.append(price * 0.995)
            else:
                highs.append(price * 1.015)
                lows.append(price * 0.985)
        volumes = [1500] * 55 + [900, 850, 820, 780, 740, 700, 710, 720, 730, 760]

        result = evaluate_symbol(
            symbol="159770",
            name="机器人ETF",
            instrument_type="etf",
            frame=self._frame(closes, volumes, highs, lows),
            mode="close_confirmed",
        )

        self.assertNotEqual(result.group, "触发买点")
        self.assertNotEqual(result.setup, "MA40 弹簧压紧后松开")

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
            [10.2] * 30
            + [10.0, 9.8, 9.65, 9.5, 9.6, 9.8, 10.0, 10.2, 10.4, 10.5]
            + [10.4, 10.3, 10.2, 10.1, 10.0, 9.9, 9.8, 9.7, 9.6, 9.5]
            + [9.65, 9.7, 9.8, 9.92, 10.0, 10.08, 10.14, 10.18, 10.22, 10.26]
        )
        volumes = (
            [1000] * 30
            + [1500, 1450, 1400, 1350, 1300, 1250, 1200, 1180, 1160, 1140]
            + [1080, 1060, 1040, 1020, 1000, 980, 960, 940, 920, 900]
            + [880, 860, 840, 860, 900, 940, 980, 1020, 1040, 1060]
        )
        highs = [price * 1.002 for price in closes]
        lows = [price * 0.998 for price in closes]

        result = evaluate_symbol(
            symbol="300124",
            name="汇川技术",
            instrument_type="stock",
            frame=self._frame(closes, volumes, highs, lows),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "触发买点")
        self.assertIn("双底", result.setup)

    def test_should_not_trigger_double_bottom_without_meaningful_rebound_or_breakout(self):
        closes = (
            [10.0] * 15
            + [9.8, 9.6, 9.4, 9.2, 9.0, 9.1, 9.2, 9.3, 9.25, 9.2]
            + [9.15, 9.1, 9.2, 9.25, 9.2, 9.15, 9.1, 9.05, 9.0, 9.1]
            + [9.2, 9.3, 9.35, 9.4, 9.45, 9.5, 9.48, 9.46, 9.44, 9.42]
            + [9.4, 9.38, 9.36, 9.34, 9.32]
        )

        result = evaluate_symbol(
            symbol="300750",
            name="测试标的",
            instrument_type="stock",
            frame=self._frame(closes),
            mode="close_confirmed",
        )

        self.assertNotEqual(result.group, "触发买点")
        self.assertNotEqual(result.setup, "双底或二次压紧")

    def test_should_not_pair_across_intervening_lower_low_for_double_bottom(self):
        closes = (
            [10.4] * 12
            + [10.2, 9.9, 9.5, 9.2, 9.0, 9.2, 9.5, 9.9, 10.2, 10.4]
            + [10.1, 9.8, 9.2, 8.7, 8.2, 8.0, 8.2, 8.5, 8.8, 9.1]
            + [9.2, 9.1, 9.0, 8.95, 8.92, 9.0, 9.1, 9.2, 9.3, 9.45]
            + [9.5, 9.55, 9.6, 9.62, 9.58, 9.6, 9.65, 9.7]
        )
        volumes = (
            [1000] * 12
            + [1400, 1350, 1300, 1250, 1200, 1180, 1160, 1140, 1120, 1100]
            + [1500, 1480, 1460, 1440, 1420, 1400, 1380, 1360, 1340, 1320]
            + [950, 930, 910, 890, 870, 860, 850, 840, 830, 820]
            + [900, 920, 940, 960, 950, 940, 930, 920]
        )

        result = evaluate_symbol(
            symbol="002340",
            name="格林美样例",
            instrument_type="stock",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertNotEqual(result.setup, "双底或二次压紧")
        self.assertNotEqual(result.group, "触发买点")

    def test_should_use_newer_lower_low_as_left_bottom_for_double_bottom(self):
        closes = (
            [10.6] * 14
            + [10.3, 10.0, 9.7, 9.4, 9.1, 9.0, 9.2, 9.5, 9.8, 10.0]
            + [9.9, 9.6, 9.3, 8.95, 8.8, 8.86, 9.0, 9.3, 9.6, 9.9]
            + [10.0, 10.2, 10.1, 9.95, 9.8, 9.65, 9.5, 9.35, 9.2, 9.0]
            + [9.1, 9.25, 9.4, 9.55, 9.7, 9.82, 9.9, 9.96, 10.02, 10.08]
        )
        volumes = (
            [1000] * 14
            + [1500, 1450, 1400, 1350, 1300, 1250, 1200, 1160, 1120, 1080]
            + [1500, 1480, 1460, 1420, 1380, 1360, 1320, 1280, 1240, 1200]
            + [1040, 1020, 1000, 980, 960, 940, 920, 900, 880, 860]
            + [900, 920, 940, 960, 980, 1000, 1020, 1040, 1060, 1080]
        )

        candidate = _double_bottom_candidate(enrich_daily_indicators(self._frame(closes, volumes)))

        self.assertIsNotNone(candidate)
        self.assertAlmostEqual(float(candidate["first_low"]), 8.712, places=3)
        self.assertAlmostEqual(float(candidate["second_low"]), 8.91, places=2)

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
        self.assertIn("近10日振幅收敛", result.signals)

    def test_should_not_trigger_launch_candle_on_second_day_after_breakout(self):
        closes = [10.0 + (index % 2) * 0.1 for index in range(59)] + [10.8, 11.5]
        volumes = [1000] * 59 + [1800, 2200]

        result = evaluate_symbol(
            symbol="002747",
            name="埃斯顿",
            instrument_type="stock",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertNotEqual(result.setup, "整理后第一根启动阳线")
        self.assertNotEqual(result.group, "触发买点")

    def test_should_downgrade_trigger_to_focus_when_risk_to_stop_is_above_twelve_percent(self):
        closes = [10.0 + (index % 2) * 0.1 for index in range(60)] + [11.4]
        volumes = [1000] * 60 + [1800]

        result = evaluate_symbol(
            symbol="002747",
            name="埃斯顿",
            instrument_type="stock",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "重点观察")
        self.assertAlmostEqual(result.risk_to_stop_pct, 15.15, places=2)

    def test_should_downgrade_to_wait_when_risk_to_stop_is_above_eighteen_percent(self):
        closes = [10.0 + (index % 2) * 0.1 for index in range(60)] + [12.0]
        volumes = [1000] * 60 + [1800]

        result = evaluate_symbol(
            symbol="002747",
            name="埃斯顿",
            instrument_type="stock",
            frame=self._frame(closes, volumes),
            mode="close_confirmed",
        )

        self.assertEqual(result.group, "等待回调")
        self.assertAlmostEqual(result.risk_to_stop_pct, 21.21, places=2)


if __name__ == "__main__":
    unittest.main()
