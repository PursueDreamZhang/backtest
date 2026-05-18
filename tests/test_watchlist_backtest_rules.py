import unittest

from watchlist_backtest.rules import (
    should_close_position,
    should_close_position_tplus1,
    should_open_position,
    should_open_position_by_price_touch,
)


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

    def test_should_allow_price_touch_signal_with_reasonable_risk(self):
        decision = should_open_position_by_price_touch(
            {"group": "触发买点", "stop_loss": 9.5, "trigger_price": 10.0},
            {"low": 9.8, "high": 10.2},
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "ok")

    def test_should_reject_price_touch_when_trigger_not_hit(self):
        decision = should_open_position_by_price_touch(
            {"group": "触发买点", "stop_loss": 9.5, "trigger_price": 10.0},
            {"low": 9.6, "high": 9.99},
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "trigger_not_touched")


    def test_should_close_tplus1_stop_loss_at_open_before_intraday_stop(self):
        decision = should_close_position_tplus1(
            {"stop_loss": 9.0, "holding_days": 1},
            {"open": 8.8, "low": 8.7, "close": 9.1},
            None,
            max_hold_days=10,
        )
        self.assertTrue(decision.should_close)
        self.assertEqual(decision.reason, "stop_loss")
        self.assertEqual(decision.exit_price, 8.8)

    def test_should_not_stop_on_entry_day_under_tplus1_rule(self):
        decision = should_close_position_tplus1(
            {"stop_loss": 9.0, "holding_days": 0},
            {"open": 10.0, "low": 8.8, "close": 9.1},
            None,
            max_hold_days=10,
        )
        self.assertFalse(decision.should_close)
        self.assertEqual(decision.reason, "hold")
