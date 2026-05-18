import unittest

import pandas as pd

from watchlist_backtest.signal_diary import compute_trigger_price


class WatchlistBacktestSignalDiaryTests(unittest.TestCase):
    def test_should_use_signal_day_close_for_five_percent_trigger_setups(self):
        frame = pd.DataFrame(
            [
                {"open": 9.8, "high": 10.1, "low": 9.7, "close": 10.0, "ma20": 9.5},
            ],
            index=pd.to_datetime(["2026-04-01"]),
        )

        trigger_price, rule = compute_trigger_price(
            {"group": "触发买点", "setup": "双底或二次压紧", "latest_price": 10.0},
            frame,
        )

        self.assertEqual(rule, "prev_close_x_1.05")
        self.assertAlmostEqual(trigger_price, 10.5)

    def test_should_use_signal_day_ma20_for_ma20_first_pullback(self):
        frame = pd.DataFrame(
            [
                {"open": 9.8, "high": 10.1, "low": 9.7, "close": 10.0, "ma20": 9.66},
            ],
            index=pd.to_datetime(["2026-04-01"]),
        )

        trigger_price, rule = compute_trigger_price(
            {"group": "触发买点", "setup": "MA20 第一次回档", "latest_price": 10.0},
            frame,
        )

        self.assertEqual(rule, "signal_day_ma20")
        self.assertAlmostEqual(trigger_price, 9.66)

    def test_should_return_none_for_non_trigger_group(self):
        frame = pd.DataFrame(
            [
                {"open": 9.8, "high": 10.1, "low": 9.7, "close": 10.0, "ma20": 9.66},
            ],
            index=pd.to_datetime(["2026-04-01"]),
        )

        trigger_price, rule = compute_trigger_price(
            {"group": "重点观察", "setup": "MA20 第一次回档", "latest_price": 10.0},
            frame,
        )

        self.assertIsNone(trigger_price)
        self.assertIsNone(rule)
