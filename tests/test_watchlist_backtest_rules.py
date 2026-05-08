import unittest

from watchlist_backtest.rules import should_close_position, should_open_position


class WatchlistBacktestRulesTests(unittest.TestCase):
    def test_should_allow_trigger_signal_with_reasonable_risk(self):
        decision = should_open_position(
            {"group": "触发买点", "stop_loss": 9.0},
            10.0,
        )
        self.assertTrue(decision.allowed)

    def test_should_reject_signal_when_open_is_too_far_from_stop(self):
        decision = should_open_position(
            {"group": "触发买点", "stop_loss": 8.0},
            10.0,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "too_far_from_stop")

    def test_should_close_on_stop_loss(self):
        decision = should_close_position(
            {"stop_loss": 9.0, "holding_days": 1},
            {"low": 8.9, "open": 10.0, "close": 9.1},
            None,
            max_hold_days=10,
        )
        self.assertTrue(decision.should_close)
        self.assertEqual(decision.reason, "stop_loss")

