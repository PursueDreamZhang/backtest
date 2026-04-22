import unittest

import pandas as pd

from research.market_regime import (
    build_composite_benchmark,
    build_daily_state,
    build_feature_table,
    build_leaderboard,
)


class CompositeBenchmarkTests(unittest.TestCase):
    def test_should_build_equal_weight_composite_benchmark_from_market_proxies(self):
        index = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        frames = {
            "A": pd.DataFrame(
                {
                    "open": [100.0, 110.0, 120.0],
                    "high": [101.0, 111.0, 121.0],
                    "low": [99.0, 109.0, 119.0],
                    "close": [100.0, 110.0, 120.0],
                    "volume": [1000.0, 1000.0, 1000.0],
                },
                index=index,
            ),
            "B": pd.DataFrame(
                {
                    "open": [200.0, 220.0, 240.0],
                    "high": [202.0, 222.0, 242.0],
                    "low": [198.0, 218.0, 238.0],
                    "close": [200.0, 220.0, 240.0],
                    "volume": [3000.0, 3000.0, 3000.0],
                },
                index=index,
            ),
        }

        benchmark = build_composite_benchmark(frames, ["A", "B"])

        self.assertEqual(list(benchmark.columns), ["open", "high", "low", "close", "volume"])
        self.assertAlmostEqual(benchmark.iloc[0]["close"], 1.0)
        self.assertAlmostEqual(benchmark.iloc[1]["close"], 1.1)
        self.assertAlmostEqual(benchmark.iloc[2]["close"], 1.2)
        self.assertAlmostEqual(benchmark.iloc[0]["volume"], 2000.0)

    def test_should_use_available_market_proxies_only_on_each_date(self):
        index_a = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
        index_b = pd.to_datetime(["2024-01-03", "2024-01-04"])
        frames = {
            "A": pd.DataFrame(
                {
                    "open": [100.0, 110.0, 120.0],
                    "high": [100.0, 110.0, 120.0],
                    "low": [100.0, 110.0, 120.0],
                    "close": [100.0, 110.0, 120.0],
                    "volume": [1000.0, 1000.0, 1000.0],
                },
                index=index_a,
            ),
            "B": pd.DataFrame(
                {
                    "open": [200.0, 220.0],
                    "high": [200.0, 220.0],
                    "low": [200.0, 220.0],
                    "close": [200.0, 220.0],
                    "volume": [3000.0, 3000.0],
                },
                index=index_b,
            ),
        }

        benchmark = build_composite_benchmark(frames, ["A", "B"])

        self.assertEqual(len(benchmark), 3)
        self.assertAlmostEqual(benchmark.loc[pd.Timestamp("2024-01-02"), "close"], 1.0)
        self.assertAlmostEqual(benchmark.loc[pd.Timestamp("2024-01-03"), "close"], 1.05)

    def test_should_build_features_and_state_from_benchmark_frame(self):
        index = pd.date_range("2024-01-01", periods=80, freq="B")
        benchmark_frame = pd.DataFrame(
            {
                "open": [1 + i * 0.01 for i in range(80)],
                "high": [1.01 + i * 0.01 for i in range(80)],
                "low": [0.99 + i * 0.01 for i in range(80)],
                "close": [1 + i * 0.01 for i in range(80)],
                "volume": [1000 + i for i in range(80)],
            },
            index=index,
        )
        frames = {
            "510050": pd.DataFrame(
                {
                    "open": [10 + i * 0.1 for i in range(80)],
                    "high": [10.1 + i * 0.1 for i in range(80)],
                    "low": [9.9 + i * 0.1 for i in range(80)],
                    "close": [10 + i * 0.1 for i in range(80)],
                    "volume": [10000 + i for i in range(80)],
                },
                index=index,
            ),
            "159915": pd.DataFrame(
                {
                    "open": [10 + i * 0.15 for i in range(80)],
                    "high": [10.1 + i * 0.15 for i in range(80)],
                    "low": [9.9 + i * 0.15 for i in range(80)],
                    "close": [10 + i * 0.15 for i in range(80)],
                    "volume": [12000 + i for i in range(80)],
                },
                index=index,
            ),
        }
        params = {
            "relative_strength_windows": [20, 40, 60],
            "momentum_windows": [5, 10, 20],
            "short_ma": 20,
            "long_ma": 40,
            "short_volume_window": 5,
            "long_volume_window": 20,
            "weights": {
                "relative_strength_score": 0.30,
                "momentum_score": 0.25,
                "volume_price_score": 0.25,
                "trend_support_score": 0.10,
                "stability_score": 0.10,
            },
            "market_weights": {
                "trend": 0.25,
                "breadth": 0.25,
                "volume_confirmation": 0.25,
                "cooldown_risk": 0.25,
            },
        }

        features = build_feature_table(frames, benchmark_frame=benchmark_frame, params=params)
        leaderboard = build_leaderboard(features, params=params)
        daily_state = build_daily_state(
            frames,
            leaderboard,
            benchmark_frame=benchmark_frame,
            params=params,
        )

        self.assertIn("relative_strength_score", features.columns)
        self.assertGreater(len(daily_state), 0)
        self.assertIn("market_stage_score", daily_state.columns)

    def test_should_allow_market_trend_score_to_reach_one(self):
        index = pd.date_range("2024-01-01", periods=80, freq="B")
        benchmark_frame = pd.DataFrame(
            {
                "open": [1 + i * 0.02 for i in range(80)],
                "high": [1.01 + i * 0.02 for i in range(80)],
                "low": [0.99 + i * 0.02 for i in range(80)],
                "close": [1 + i * 0.02 for i in range(80)],
                "volume": [1000 + i for i in range(80)],
            },
            index=index,
        )
        frames = {
            "A": pd.DataFrame(
                {
                    "open": [10 + i * 0.10 for i in range(80)],
                    "high": [10.1 + i * 0.10 for i in range(80)],
                    "low": [9.9 + i * 0.10 for i in range(80)],
                    "close": [10 + i * 0.10 for i in range(80)],
                    "volume": [1000 + i for i in range(80)],
                },
                index=index,
            ),
            "B": pd.DataFrame(
                {
                    "open": [10 + i * 0.12 for i in range(80)],
                    "high": [10.1 + i * 0.12 for i in range(80)],
                    "low": [9.9 + i * 0.12 for i in range(80)],
                    "close": [10 + i * 0.12 for i in range(80)],
                    "volume": [1200 + i for i in range(80)],
                },
                index=index,
            ),
        }
        params = {
            "relative_strength_windows": [20, 40, 60],
            "momentum_windows": [5, 10, 20],
            "short_ma": 20,
            "long_ma": 40,
            "short_volume_window": 5,
            "long_volume_window": 20,
            "weights": {
                "relative_strength_score": 0.30,
                "momentum_score": 0.25,
                "volume_price_score": 0.25,
                "trend_support_score": 0.10,
                "stability_score": 0.10,
            },
            "market_weights": {
                "trend": 0.25,
                "breadth": 0.25,
                "volume_confirmation": 0.25,
                "cooldown_risk": 0.25,
            },
        }

        features = build_feature_table(frames, benchmark_frame=benchmark_frame, params=params)
        leaderboard = build_leaderboard(features, params=params)
        daily_state = build_daily_state(
            frames,
            leaderboard,
            benchmark_frame=benchmark_frame,
            params=params,
        )

        self.assertEqual(float(daily_state["market_trend_score"].max()), 1.0)

    def test_should_use_raw_trend_and_volume_signals_for_market_state(self):
        index = pd.to_datetime(["2024-02-01"])
        leaderboard = pd.DataFrame(
            {
                "date": index.repeat(3),
                "symbol": ["A", "B", "C"],
                "trend_support_score": [0.9, 0.8, 0.7],
                "trend_support_score_raw": [2.0, 2.0, 0.0],
                "volume_price_score": [0.9, 0.4, 0.2],
                "volume_price_score_raw": [1.2, 1.1, 0.8],
                "composite_score": [0.9, 0.8, 0.7],
                "rank": [1.0, 2.0, 3.0],
            }
        )
        benchmark_index = pd.date_range("2023-11-01", periods=80, freq="B")
        benchmark_frame = pd.DataFrame(
            {
                "open": [1 + i * 0.02 for i in range(80)],
                "high": [1.01 + i * 0.02 for i in range(80)],
                "low": [0.99 + i * 0.02 for i in range(80)],
                "close": [1 + i * 0.02 for i in range(80)],
                "volume": [1000 + i for i in range(80)],
            },
            index=benchmark_index,
        )
        params = {
            "short_ma": 20,
            "long_ma": 40,
            "market_weights": {
                "trend": 0.25,
                "breadth": 0.25,
                "volume_confirmation": 0.25,
                "cooldown_risk": 0.25,
            },
        }

        daily_state = build_daily_state(
            {},
            leaderboard,
            benchmark_frame=benchmark_frame,
            params=params,
        )

        self.assertAlmostEqual(float(daily_state.iloc[0]["market_breadth_score"]), 2 / 3)
        self.assertAlmostEqual(float(daily_state.iloc[0]["volume_confirmation_score"]), 2 / 3)

    def test_should_classify_retreat_when_cooldown_and_structure_weaken(self):
        state_date = pd.Timestamp("2024-02-20")
        leaderboard = pd.DataFrame(
            {
                "date": [state_date, state_date, state_date],
                "symbol": ["A", "B", "C"],
                "trend_support_score": [0.3, 0.2, 0.1],
                "trend_support_score_raw": [0.0, 0.0, 0.0],
                "volume_price_score": [0.7, 0.6, 0.5],
                "volume_price_score_raw": [0.9, 0.9, 0.8],
                "composite_score": [0.90, 0.80, 0.70],
                "rank": [1.0, 2.0, 3.0],
            }
        )
        benchmark_index = pd.date_range("2023-11-01", periods=80, freq="B")
        benchmark_closes = [100 + i for i in range(70)] + [167, 166, 165, 164, 162, 160, 159, 158, 156, 153]
        benchmark_frame = pd.DataFrame(
            {
                "open": benchmark_closes,
                "high": [value + 1 for value in benchmark_closes],
                "low": [value - 1 for value in benchmark_closes],
                "close": benchmark_closes,
                "volume": [1000 + i for i in range(80)],
            },
            index=benchmark_index,
        )
        params = {
            "short_ma": 20,
            "long_ma": 40,
            "market_weights": {
                "trend": 0.25,
                "breadth": 0.25,
                "volume_confirmation": 0.25,
                "cooldown_risk": 0.25,
            },
        }

        daily_state = build_daily_state(
            {},
            leaderboard,
            benchmark_frame=benchmark_frame,
            params=params,
        )

        self.assertEqual(daily_state.iloc[0]["market_stage"], "退潮")


if __name__ == "__main__":
    unittest.main()
