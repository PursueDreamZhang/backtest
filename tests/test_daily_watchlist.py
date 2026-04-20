import os
import sys
import unittest

import pandas as pd

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
SCRIPTS_DIR = os.path.join(PROJECT_ROOT, 'scripts')
if SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, SCRIPTS_DIR)

from daily_watchlist import _yearly_market_file, evaluate_watch_candidate


class TestDailyWatchlist(unittest.TestCase):
    def test_should_point_yearly_cache_to_market_data_directory(self):
        yearly_file = _yearly_market_file('510300', 2026)

        self.assertIn('yearly_market_data', str(yearly_file))
        self.assertTrue(str(yearly_file).endswith('data/yearly_market_data/2026/510300.pkl'))

    def test_should_identify_watch_candidate_when_stage_one_and_stage_two_match(self):
        rows = []
        for _ in range(10):
            close = 10.0
            rows.append({'open': close, 'high': 10.2, 'low': 9.8, 'close': close, 'volume': 1000})

        close = 10.0
        for _ in range(20):
            close += 0.4
            rows.append({'open': close, 'high': close * 1.03, 'low': close * 0.99, 'close': close, 'volume': 1000})

        for _ in range(5):
            close -= 0.36
            rows.append({'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 1000})

        for _ in range(10):
            rows.append({'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 1000})

        df = pd.DataFrame(rows, index=pd.date_range('2026-01-01', periods=len(rows), freq='B'))
        result = evaluate_watch_candidate(
            df,
            {
                'surge_period': 30,
                'surge_threshold': 0.5,
                'ma_period': 40,
                'ma_short_period': 20,
                'ma_exit_period': 10,
                'support_lookback': 20,
                'support_range': 0.05,
                'volume_shrink_ratio': 0.80,
                'breakout_pct': 0.05,
                'stop_loss': 0.10,
                'profit_threshold': 0.03,
                'hold_days': 2,
                'drop_threshold': 0.05,
            },
        )

        self.assertIsNotNone(result)
        self.assertGreater(result['surge_30_pct'], 50)
        self.assertGreater(result['distance_from_peak_pct'], 5)
        self.assertLessEqual(result['support_distance_pct'], 5)

    def test_should_reject_when_not_strong_enough(self):
        rows = []
        close = 10.0
        for _ in range(60):
            rows.append({'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 1000})
            close += 0.03

        df = pd.DataFrame(rows, index=pd.date_range('2026-01-01', periods=len(rows), freq='B'))
        result = evaluate_watch_candidate(
            df,
            {
                'surge_period': 30,
                'surge_threshold': 0.5,
                'ma_period': 40,
                'ma_short_period': 20,
                'ma_exit_period': 10,
                'support_lookback': 20,
                'support_range': 0.05,
                'volume_shrink_ratio': 0.80,
                'breakout_pct': 0.05,
                'stop_loss': 0.10,
                'profit_threshold': 0.03,
                'hold_days': 2,
                'drop_threshold': 0.05,
            },
        )

        self.assertIsNone(result)

    def test_should_not_mark_candidate_when_replay_has_already_bought(self):
        rows = []

        for _ in range(10):
            close = 10.0
            rows.append({'open': close, 'high': 10.1, 'low': 9.9, 'close': close, 'volume': 1000})

        close = 10.0
        for _ in range(20):
            close += 0.45
            rows.append({'open': close, 'high': close * 1.06, 'low': close * 0.99, 'close': close, 'volume': 1000})

        for _ in range(5):
            close -= 0.2
            rows.append({'open': close, 'high': close * 1.06, 'low': close * 0.99, 'close': close, 'volume': 600})

        for _ in range(20):
            close += 0.1
            rows.append({'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 900})

        df = pd.DataFrame(rows, index=pd.date_range('2026-01-01', periods=len(rows), freq='B'))
        result = evaluate_watch_candidate(
            df,
            {
                'surge_period': 30,
                'surge_threshold': 0.5,
                'ma_period': 40,
                'ma_short_period': 20,
                'ma_exit_period': 10,
                'support_lookback': 20,
                'support_range': 0.05,
                'volume_shrink_ratio': 0.80,
                'breakout_pct': 0.05,
                'stop_loss': 0.10,
                'profit_threshold': 0.03,
                'hold_days': 2,
                'drop_threshold': 0.05,
            },
        )

        self.assertIsNone(result)

    def test_should_not_mark_candidate_when_current_30_day_surge_is_below_threshold(self):
        rows = []

        for _ in range(10):
            close = 10.0
            rows.append({'open': close, 'high': 10.1, 'low': 9.9, 'close': close, 'volume': 1000})

        close = 10.0
        for _ in range(20):
            close += 0.45
            rows.append({'open': close, 'high': close * 1.03, 'low': close * 0.99, 'close': close, 'volume': 1000})

        close = 12.5
        for _ in range(35):
            rows.append({'open': close, 'high': 12.6, 'low': 12.4, 'close': close, 'volume': 1000})

        for _ in range(5):
            rows.append({'open': close, 'high': close * 1.01, 'low': close * 0.99, 'close': close, 'volume': 1000})

        df = pd.DataFrame(rows, index=pd.date_range('2026-01-01', periods=len(rows), freq='B'))
        result = evaluate_watch_candidate(
            df,
            {
                'surge_period': 30,
                'surge_threshold': 0.5,
                'ma_period': 40,
                'ma_short_period': 20,
                'ma_exit_period': 10,
                'support_lookback': 20,
                'support_range': 0.05,
                'volume_shrink_ratio': 0.80,
                'breakout_pct': 0.05,
                'stop_loss': 0.10,
                'profit_threshold': 0.03,
                'hold_days': 2,
                'drop_threshold': 0.05,
            },
        )

        self.assertIsNone(result)


if __name__ == '__main__':
    unittest.main()
