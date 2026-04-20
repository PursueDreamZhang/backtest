import unittest

import pandas as pd

from research.market_regime import build_daily_state, build_feature_table, build_leaderboard


def _frame(values, volumes):
    idx = pd.date_range('2026-01-01', periods=len(values), freq='B')
    return pd.DataFrame(
        {
            'open': values,
            'high': [x * 1.01 for x in values],
            'low': [x * 0.99 for x in values],
            'close': values,
            'volume': volumes,
        },
        index=idx,
    )


class TestMarketRegimeScores(unittest.TestCase):
    def test_should_rank_semiconductor_etf_first_when_relative_strength_and_volume_are_strongest(self):
        frames = {
            '510300': _frame([100 + i * 0.3 for i in range(80)], [1000] * 80),
            '512480': _frame([100 + i * 0.8 for i in range(80)], [900 + i * 8 for i in range(80)]),
            '512010': _frame([100 + i * 0.2 for i in range(80)], [1000] * 80),
        }
        params = {
            'relative_strength_windows': [20, 40, 60],
            'momentum_windows': [5, 10, 20],
            'short_ma': 20,
            'long_ma': 40,
            'short_volume_window': 5,
            'long_volume_window': 20,
            'weights': {
                'relative_strength': 0.30,
                'momentum': 0.25,
                'volume_price': 0.25,
                'trend_support': 0.10,
                'stability': 0.10,
            },
        }

        features = build_feature_table(frames, benchmark_symbol='510300', params=params)
        leaderboard = build_leaderboard(features)
        last_day = leaderboard['date'].max()
        top1 = leaderboard.loc[leaderboard['date'] == last_day].sort_values('rank').iloc[0]

        self.assertEqual(top1['symbol'], '512480')
        self.assertEqual(int(top1['rank']), 1)

    def test_should_mark_market_as_rally_when_breadth_volume_and_leader_gap_are_all_strong(self):
        frames = {
            '510300': _frame([100 + i * 0.3 for i in range(100)], [1000] * 100),
            '512480': _frame([100 + i * 0.8 for i in range(100)], [1200 + i * 10 for i in range(100)]),
            '512010': _frame([100 + i * 0.5 for i in range(100)], [1100 + i * 8 for i in range(100)]),
            '512660': _frame([100 + i * 0.45 for i in range(100)], [1080 + i * 8 for i in range(100)]),
        }
        params = {
            'relative_strength_windows': [20, 40, 60],
            'momentum_windows': [5, 10, 20],
            'short_ma': 20,
            'long_ma': 40,
            'short_volume_window': 5,
            'long_volume_window': 20,
            'weights': {
                'relative_strength': 0.30,
                'momentum': 0.25,
                'volume_price': 0.25,
                'trend_support': 0.10,
                'stability': 0.10,
            },
            'market_weights': {
                'trend': 0.25,
                'breadth': 0.25,
                'volume_confirmation': 0.25,
                'cooldown_risk': 0.25,
            },
        }

        features = build_feature_table(frames, benchmark_symbol='510300', params=params)
        leaderboard = build_leaderboard(features)
        daily_state = build_daily_state(frames, leaderboard, benchmark_symbol='510300', params=params)

        last_day = daily_state.iloc[-1]
        self.assertEqual(last_day['market_stage'], '主升')
        self.assertTrue(bool(last_day['can_open_new_position']))
        self.assertEqual(last_day['leader_etf_top1'], '512480')


if __name__ == '__main__':
    unittest.main()
